"""HDRI environment maps: Poly Haven and ambientCG downloads, cached and logged.

Spec strings: `polyhaven:<slug>` (e.g. `polyhaven:studio_small_09`),
`ambientcg:<id>` (e.g. `ambientcg:StudioSmall09`), `none`, or an absolute
local path. Both sources are CC0; the caller records the license via `on_asset`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from logo_maker.paths import cache_dir

AssetCallback = Callable[..., None]


class HdriError(ValueError):
    """The HDRI spec names nothing downloadable."""


def fetch(
    spec: str, *, on_asset: AssetCallback | None = None, timeout: float = 120.0
) -> Path | None:
    """Download (or locate) the HDRI for `spec`; `none` returns None."""
    if spec == "none":
        return None
    if spec.startswith("polyhaven:"):
        return _polyhaven(spec.split(":", 1)[1], on_asset=on_asset, timeout=timeout)
    if spec.startswith("ambientcg:"):
        return _ambientcg(spec.split(":", 1)[1], on_asset=on_asset, timeout=timeout)
    path = Path(spec)
    if path.is_absolute() and path.exists():
        return path
    raise HdriError(
        f"hdri spec {spec!r} is not polyhaven:<slug>, ambientcg:<id>, "
        f"none, or an existing absolute path"
    )


def _download(url: str, dest: Path, timeout: float) -> Path:
    import httpx

    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in resp.iter_bytes():
                    fh.write(chunk)
    except Exception as exc:
        if dest.exists():
            dest.unlink(missing_ok=True)
        raise HdriError(f"could not download {url}: {exc}") from exc
    return dest


def _polyhaven(slug: str, *, on_asset: AssetCallback | None, timeout: float) -> Path:
    """One 1k HDR from the Poly Haven API (https://api.polyhaven.com/files/<slug>)."""
    import httpx

    try:
        resp = httpx.get(f"https://api.polyhaven.com/files/{slug}", timeout=timeout)
        resp.raise_for_status()
        files = resp.json()["hdri"]
    except Exception as exc:
        raise HdriError(f"Poly Haven has no files for {slug!r}: {exc}") from exc
    for quality in ("1k", "2k", "4k"):
        if quality in files and "hdr" in files[quality]:
            url = files[quality]["hdr"]["url"]
            break
    else:
        raise HdriError(f"Poly Haven {slug!r} offers no HDR download")
    dest = cache_dir("hdri") / f"polyhaven_{slug}.hdr"
    _download(url, dest, timeout)
    if on_asset is not None:
        on_asset(
            f"hdri:{slug}",
            source=f"https://polyhaven.com/a/{slug}",
            license="CC0-1.0",
            path=str(dest),
        )
    return dest


def _ambientcg(asset_id: str, *, on_asset: AssetCallback | None, timeout: float) -> Path:
    """One 1k HDR-JPG from the ambientCG API v3."""
    import httpx

    info_url = f"https://ambientcg.com/api/v3/full/{asset_id}"
    try:
        resp = httpx.get(info_url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        downloads = data.get("downloadUrls", data.get("downloads", {}))
        url = _pick_ambient_url(downloads, asset_id)
    except Exception as exc:
        raise HdriError(f"ambientCG has no asset {asset_id!r}: {exc}") from exc
    dest = cache_dir("hdri") / f"ambientcg_{asset_id}.hdr"
    _download(url, dest, timeout)
    if on_asset is not None:
        on_asset(
            f"hdri:{asset_id}",
            source=f"https://ambientcg.com/view?id={asset_id}",
            license="CC0-1.0",
            path=str(dest),
        )
    return dest


def _pick_ambient_url(downloads: object, asset_id: str) -> str:
    if isinstance(downloads, str):
        return downloads
    if isinstance(downloads, dict):
        for key in ("1K-HDR", "1k-hdr", "HDR", "hdr"):
            if key in downloads and isinstance(downloads[key], str):
                return downloads[key]
        for value in downloads.values():
            if isinstance(value, str) and value.startswith("http"):
                return value
    raise HdriError(f"ambientCG asset {asset_id!r} exposes no direct HDR URL")
