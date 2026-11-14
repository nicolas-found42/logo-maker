"""Download one attributable photo at a time in the campaign network profile."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import httpx
from PIL import Image

from logo_maker import study
from logo_maker.sampling_diagnostics import sha256


def source_domain(url: str) -> str:
    source = urlsplit(url)
    host = source.hostname or ""
    if (
        source.scheme != "https"
        or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.[a-z][a-z0-9-]*", host)
        or source.username is not None
        or source.port not in (None, 443)
        or host.endswith((".localhost", ".local", ".internal"))
    ):
        raise ValueError("reference acquisition requires a direct public HTTPS URL")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    raise ValueError("reference acquisition requires a public DNS name")


def fetch(logo, record: dict, budget) -> dict:
    url = record["url"]
    domain = source_domain(url)
    if not all(
        isinstance(record.get(key), str) and record[key].strip()
        for key in ("url", "source", "license")
    ):
        raise ValueError("record the photo source and license")
    folder = study._safe(logo.root, "reference-downloads")
    folder.mkdir(exist_ok=True)
    cap = 24 * 1024 * 1024
    with TemporaryDirectory(prefix=".photo-", dir=folder) as temporary_dir:
        temporary = Path(temporary_dir) / "download"
        with (
            temporary.open("wb") as file,
            httpx.stream(
                "GET",
                url,
                follow_redirects=False,
                timeout=20,
                headers={
                    "User-Agent": "LogoMaker/0.1 (https://github.com/nicolas-found42/logo-maker)",
                    "Accept": "image/jpeg,image/png,image/webp",
                },
            ) as response,
        ):
            if response.is_redirect:
                raise ValueError("use the final image URL so its domain can be explicitly allowed")
            if response.status_code != 200:
                raise RuntimeError(f"{domain} returned HTTP {response.status_code} for this photo.")
            received = 0
            for chunk in response.iter_bytes():
                budget.check()
                received += len(chunk)
                if received > cap:
                    raise ValueError("reference exceeds the 24 MiB download limit")
                file.write(chunk)
        with Image.open(temporary) as image:
            extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(image.format)
            if extension is None:
                raise ValueError("reference must be a JPEG, PNG or WebP image")
            image.verify()
        digest = sha256(temporary)
        target = folder / (digest + extension)
        temporary.replace(target)
    return {
        "path": target.relative_to(logo.root).as_posix(),
        "sha256": digest,
        "url": url,
        "domain": domain,
        "source": record["source"],
        "license": record["license"],
    }
