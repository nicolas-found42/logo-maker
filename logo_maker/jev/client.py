"""Jev transport: typed questions to TypeSafe's System One model, with full request logging.

Jev makes judgments; code decides. This module only sends questions and returns
answers. Every truth table lives in `questions.py` or the calling stage.

Two transports, chosen by environment:
- `TYPESAFE_API_KEY` set -> POST https://api.typesafe.ai/v1/systemone, model `jev-1.14`.
- else `OPENROUTER_API_KEY` set -> POST https://openrouter.ai/api/alpha/decisions,
  model `typesafe/jev-1.14` (verified working, including images).

Neither key set -> `JevError` naming both variables. An API failure is always an
error, never a "no".
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol

import httpx
from PIL import Image as _PILImage
from PIL import ImageOps as _ImageOps

from logo_maker.paths import LogoDir

TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
TYPESAFE_MODEL = "jev-1.14"
OPENROUTER_URL = "https://openrouter.ai/api/alpha/decisions"
OPENROUTER_MODEL = "typesafe/jev-1.14"

#: Hard ceiling per request (docs suggest ~64 questions/request); larger sets split.
MAX_QUESTIONS_PER_REQUEST = 60
#: Images are downscaled so the long side fits this many pixels (keeps aspect).
MAX_IMAGE_SIDE = 1024
#: The API rejects any side under 280 px, so small images are upscaled to this floor.
MIN_IMAGE_SIDE = 280
#: Statuses worth retrying with backoff.
RETRYABLE_STATUS = frozenset({429, 502, 503, 504, 529})
MAX_TRIES = 6
REQUEST_TIMEOUT = 300.0


class JevError(RuntimeError):
    """A jev request failed (no key, bad request, API error, retries exhausted)."""


class Image:
    """Marker for an image file, usable anywhere in state, instructions, or criteria.

    The client replaces each `Image` with a UUID reference and sends the bytes
    once in the request's top-level `assets` map.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def __repr__(self) -> str:
        return f"Image({self.path})"


def is_retryable(status: int | None, exc: BaseException | None = None) -> bool:
    """Whether to retry: rate limits, 5xx, 529, and network errors. All else raises."""
    if exc is not None and isinstance(exc, httpx.TransportError):
        return True
    return status in RETRYABLE_STATUS


def _load_image(path: Path) -> tuple[Any, str]:
    """Read an image file, sized to the API's 280-1568 px window; returns (PIL image, format).

    Pixels are rotated upright (EXIF is stripped, not applied, server-side), the long
    side is capped at `MAX_IMAGE_SIDE`, and any side under `MIN_IMAGE_SIDE` is upscaled.
    """
    try:
        im = _ImageOps.exif_transpose(_PILImage.open(path))
        im.load()
    except Exception as exc:
        raise JevError(f"cannot read image {path}: {exc}") from exc
    suffix = path.suffix.lower()
    wants_jpg = suffix in (".jpg", ".jpeg")
    has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if has_alpha else "RGB")
    fmt = "jpg" if wants_jpg and not has_alpha else "png"
    if max(im.size) > MAX_IMAGE_SIDE:
        im.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), _PILImage.Resampling.LANCZOS)
    if min(im.size) < MIN_IMAGE_SIDE:
        scale = MIN_IMAGE_SIDE / min(im.size)
        im = im.resize(
            (round(im.size[0] * scale), round(im.size[1] * scale)), _PILImage.Resampling.LANCZOS
        )
    return im, fmt


def _pad_to(im: Any, size: tuple[int, int]) -> Any:
    """Center `im` on a `size` canvas (transparent for alpha, white otherwise)."""
    if im.size == size:
        return im
    canvas = _PILImage.new(im.mode, size, (0, 0, 0, 0) if "A" in im.mode else (255, 255, 255))
    canvas.paste(
        im,
        ((size[0] - im.size[0]) // 2, (size[1] - im.size[1]) // 2),
    )
    return canvas


def _encode_images(images: dict[str, tuple[Any, str]]) -> dict[str, dict[str, Any]]:
    """Encode sent bytes. The API rejects mixed dimensions in one request, so when
    a request holds several images they are center-padded to the largest size."""
    target = None
    if len(images) > 1:
        sizes = {im.size for im, _ in images.values()}
        if len(sizes) > 1:
            target = (max(w for w, _ in sizes), max(h for _, h in sizes))
    encoded = {}
    for ref, (im, fmt) in images.items():
        if target is not None:
            im = _pad_to(im, target)
        buf = io.BytesIO()
        try:
            if fmt == "jpg":
                im.convert("RGB").save(buf, "JPEG", quality=92)
            else:
                im.save(buf, "PNG")
        except Exception as exc:
            raise JevError(f"cannot encode image: {exc}") from exc
        data = buf.getvalue()
        encoded[ref] = {
            "type": "image",
            "format": fmt,
            "data_base64": base64.b64encode(data).decode(),
            "_sha256": hashlib.sha256(data).hexdigest(),
            "_bytes": len(data),
            "_size": list(im.size),
        }
    return encoded


def _slug_label(label: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-") or "request"
    return slug[:80]


class JevAsker(Protocol):
    """Structural jev surface: ask one job set, or many concurrently.

    Satisfied by `JevClient` and by the test-suite fakes, so stages depend on
    the two methods they use rather than the transport.
    """

    def ask(self, state: Any, questions: dict[str, Any], *, label: str) -> dict[str, dict]: ...
    def ask_many(self, jobs: list[tuple[Any, dict[str, Any], str]]) -> list[dict[str, dict]]: ...


class JevClient:
    """Sends typed questions to jev and logs every request under the logo's qa/ dir."""

    def __init__(
        self, logo: LogoDir | None = None, *, model: str | None = None, concurrency: int = 16
    ) -> None:
        if os.environ.get("TYPESAFE_API_KEY"):
            self.url = TYPESAFE_URL
            self.model = model or TYPESAFE_MODEL
            self._key = os.environ["TYPESAFE_API_KEY"]
        elif os.environ.get("OPENROUTER_API_KEY"):
            self.url = OPENROUTER_URL
            self.model = model or OPENROUTER_MODEL
            self._key = os.environ["OPENROUTER_API_KEY"]
        else:
            raise JevError(
                "no jev API key: set TYPESAFE_API_KEY (direct TypeSafe) or "
                "OPENROUTER_API_KEY (OpenRouter); neither is set"
            )
        self.logo = logo
        self.concurrency = concurrency
        self._lock = threading.Lock()
        self._http = httpx.Client(timeout=REQUEST_TIMEOUT)
        self._seq = self._first_seq()

    def _first_seq(self) -> int:
        if self.logo is None:
            return 1
        d = self.logo.qa / "jev" / "requests"
        if not d.is_dir():
            return 1
        top = 0
        for p in d.glob("*.json"):
            m = re.match(r"(\d+)-", p.name)
            if m:
                top = max(top, int(m.group(1)))
        return top + 1

    # -- serialization ----------------------------------------------------

    def _serialize(
        self, value: Any, assets: dict[str, dict[str, Any]], pending: dict[str, tuple[Any, str]]
    ) -> Any:
        if isinstance(value, Image):
            ref = uuid.uuid4().hex
            pending[ref] = _load_image(value.path)
            assets[ref] = {"_path": str(value.path)}
            return ref
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {k: self._serialize(v, assets, pending) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._serialize(v, assets, pending) for v in value]
        return value

    # -- transport --------------------------------------------------------

    def _post(self, payload: dict[str, Any], has_images: bool) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._key}"}
        if has_images:
            headers["TypeSafe-Danger-Zone-Images"] = "true"
        last: Exception | None = None
        for attempt in range(MAX_TRIES):
            try:
                resp = self._http.post(self.url, json=payload, headers=headers)
            except httpx.TransportError as exc:
                last = exc
                if attempt < MAX_TRIES - 1:
                    time.sleep(2**attempt)
                    continue
                raise JevError(f"jev request failed after {MAX_TRIES} tries: {exc}") from exc
            if resp.status_code == 200:
                try:
                    return resp.json()  # type: ignore[no-any-return]
                except ValueError as exc:
                    raise JevError(f"jev returned non-JSON: {resp.text[:500]}") from exc
            if is_retryable(resp.status_code):
                last = None
                wait = 2**attempt
                retry_after = resp.headers.get("retry-after")
                if retry_after and retry_after.isdigit():
                    wait = max(wait, int(retry_after))
                if attempt < MAX_TRIES - 1:
                    time.sleep(wait)
                    continue
                raise JevError(
                    f"jev request failed after {MAX_TRIES} tries: HTTP {resp.status_code}"
                )
            raise JevError(f"jev request failed: HTTP {resp.status_code}: {resp.text[:2000]}")
        raise JevError(f"jev request failed after {MAX_TRIES} tries: {last}")

    @staticmethod
    def _usage(raw: dict[str, Any]) -> dict[str, Any]:
        """Reported quantities only; missing or malformed telemetry stays unknown."""
        usage = raw.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        out: dict[str, Any] = {}
        for field in ("input_tokens", "output_tokens", "cost"):
            value = usage.get(field)
            valid = type(value) is int and value >= 0
            if field == "cost" and type(value) is float:
                valid = math.isfinite(value) and value >= 0
            out[field] = value if valid else None
        return out

    # -- logging ----------------------------------------------------------

    def _store_assets(self, assets: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Write each image once under qa/jev/assets/; return stripped asset metadata."""
        if self.logo is None:
            raise JevError("logging needs a LogoDir client")
        dest = self.logo.qa / "jev" / "assets"
        dest.mkdir(parents=True, exist_ok=True)
        stripped = {}
        for ref, asset in assets.items():
            digest = asset["_sha256"]
            target = dest / f"{digest}.{asset['format']}"
            if not target.exists():
                target.write_bytes(base64.b64decode(asset["data_base64"]))
            stripped[ref] = {
                "type": "image",
                "format": asset["format"],
                "sha256": digest,
                "bytes": asset["_bytes"],
            }
        return stripped

    def _log(
        self,
        label: str,
        state: Any,
        questions: dict[str, Any],
        stripped_assets: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        if self.logo is None:
            raise JevError("logging needs a LogoDir client")
        from logo_maker.runlog import runlog

        with self._lock:
            seq = self._seq
            self._seq += 1
        record = {
            "seq": seq,
            "label": label,
            "model": self.model,
            "state": state,
            "questions": questions,
            "assets": stripped_assets,
            "status": response.get("_status", "response_received"),
            "answers": response.get("answers", {}),
            "usage": response.get("_usage", {}),
            "provider_usage": response.get("usage"),
        }
        if "_error" in response:
            record["error"] = response["_error"]
        req_dir = self.logo.qa / "jev" / "requests"
        req_dir.mkdir(parents=True, exist_ok=True)
        (req_dir / f"{seq:04d}-{_slug_label(label)}.json").write_text(json.dumps(record, indent=2))
        line = {
            "seq": seq,
            "label": label,
            "model": response.get("model", self.model),
            "questions": sorted(questions),
            "status": record["status"],
            "usage": response.get("_usage", {}),
            "answers": response.get("answers", {}),
        }
        with (self.logo.qa / "jev" / "answers.jsonl").open("a") as fh:
            fh.write(json.dumps(line, sort_keys=True) + "\n")
        runlog(self.logo.run_json).jev_usage(response.get("_usage", {}))

    # -- public API -------------------------------------------------------

    def _send_one(self, state: Any, questions: dict[str, Any], label: str) -> dict[str, dict]:
        assets: dict[str, dict[str, Any]] = {}
        pending: dict[str, tuple[Any, str]] = {}
        ser_state = self._serialize(state, assets, pending)
        ser_questions = self._serialize(questions, assets, pending)
        for ref, entry in _encode_images(pending).items():
            assets[ref].update(entry)
        body: dict[str, Any] = {"model": self.model, "state": ser_state, "questions": ser_questions}
        if assets:
            body["assets"] = {
                ref: {"type": "image", "format": a["format"], "data_base64": a["data_base64"]}
                for ref, a in assets.items()
            }
        stripped = self._store_assets(assets) if self.logo is not None else {}
        raw: dict[str, Any] = {}
        try:
            response = self._post(body, has_images=bool(assets))
            if not isinstance(response, dict):
                raise JevError("jev response must be an object")
            raw = response
            if not isinstance(raw.get("answers"), dict):
                raise JevError("jev response has no answers object")
        except JevError as exc:
            if self.logo is not None:
                raw.update(
                    _status="api_error",
                    _error=str(exc),
                    _usage=self._usage(raw),
                )
                self._log(label, ser_state, ser_questions, stripped, raw)
            raise
        usage = self._usage(raw)
        raw["_usage"] = usage
        if self.logo is not None:
            self._log(label, ser_state, ser_questions, stripped, raw)
        return raw["answers"]  # type: ignore[no-any-return]

    def ask(self, state: Any, questions: dict[str, Any], *, label: str) -> dict[str, dict]:
        """Ask one question set; splits above `MAX_QUESTIONS_PER_REQUEST` and merges."""
        if not questions:
            raise JevError(f"jev ask {label!r}: no questions")
        if len(questions) <= MAX_QUESTIONS_PER_REQUEST:
            return self._send_one(state, questions, label)
        merged: dict[str, dict] = {}
        items = list(questions.items())
        chunks = [
            dict(items[i : i + MAX_QUESTIONS_PER_REQUEST])
            for i in range(0, len(items), MAX_QUESTIONS_PER_REQUEST)
        ]
        for i, chunk in enumerate(chunks, 1):
            part = self._send_one(state, chunk, f"{label}-p{i}of{len(chunks)}")
            merged.update(part)
        return merged

    def ask_many(self, jobs: list[tuple[Any, dict[str, Any], str]]) -> list[dict[str, dict]]:
        """Ask many independent (state, questions, label) jobs concurrently, in order.

        Collects every result, then raises one `JevError` listing all failures.
        """
        results: list[dict[str, dict] | None] = [None] * len(jobs)
        failures: list[str] = []

        def run(i: int, state: Any, questions: dict[str, Any], label: str) -> None:
            try:
                results[i] = self.ask(state, questions, label=label)
            except JevError as exc:
                failures.append(f"{label}: {exc}")

        with ThreadPoolExecutor(max_workers=max(1, self.concurrency)) as pool:
            futures = [pool.submit(run, i, s, q, lab) for i, (s, q, lab) in enumerate(jobs)]
            for f in futures:
                f.result()
        if failures:
            raise JevError(
                f"{len(failures)}/{len(jobs)} jev requests failed: " + "; ".join(failures)
            )
        return [r for r in results if r is not None]
