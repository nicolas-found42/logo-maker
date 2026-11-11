"""Bounded multilayer EXR analysis. Missing passes remain unknown."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def summarize(counts: np.ndarray, rgba: np.ndarray, cap: int) -> dict:
    """Cycles Debug Sample Count is normalized by configured cap, including adaptive runs."""
    counts = counts.astype(np.float32) * cap
    if not np.isfinite(counts).all() or counts.min() < 0 or counts.max() > cap * 1.001:
        return {"status": "unknown", "reason": "invalid normalized sample counts"}
    alpha = rgba[..., 3]
    foreground = alpha > 0.01
    luminance = rgba[..., :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    masks = {
        "foreground": foreground,
        "dark": foreground & (luminance < 0.1),
        "alpha_boundary": (alpha > 0.01) & (alpha < 0.99),
    }
    # Fixed spatial tiles expose local cap saturation hidden by a frame average.
    for row in range(4):
        for col in range(4):
            mask = np.zeros_like(foreground)
            y0, y1 = row * alpha.shape[0] // 4, (row + 1) * alpha.shape[0] // 4
            x0, x1 = col * alpha.shape[1] // 4, (col + 1) * alpha.shape[1] // 4
            mask[y0:y1, x0:x1] = foreground[y0:y1, x0:x1]
            masks[f"tile_{row}_{col}"] = mask
    regions = {}
    for name, mask in masks.items():
        values = counts[mask]
        regions[name] = (
            None
            if not values.size
            else {
                "pixels": int(values.size),
                **dict(
                    zip(
                        ("p50", "p90", "p99", "max"),
                        map(float, np.quantile(values, [0.5, 0.9, 0.99, 1])),
                        strict=True,
                    )
                ),
                "near_cap_fraction": float(np.mean(values >= cap * 0.95)),
                "at_cap_fraction": float(np.mean(values >= cap - 0.5)),
            }
        )
    return {
        "status": "available",
        "normalization": "normalized X * configured cap",
        "cap": cap,
        "regions": regions,
        "noise_acceptance": "unknown",
    }


def analyze_exr(path: Path, *, cap: int, max_bytes: int) -> dict:
    """Read relevant channels across subimages with bounded decoded memory and file I/O."""
    import OpenImageIO as oiio

    unknown = {"status": "unknown", "reason": "missing, over-budget or unsupported diagnostics"}
    if not path.is_file() or path.stat().st_size > max_bytes:
        return unknown
    inp = oiio.ImageInput.open(str(path))
    if inp is None:
        return unknown
    channels: dict[str, np.ndarray] = {}
    subimages = []
    decoded = 0
    try:
        index = 0
        while inp.seek_subimage(index, 0):
            spec = inp.spec()
            names = list(spec.channelnames)
            subimages.append({"index": index, "channels": names})
            decoded += spec.width * spec.height * spec.nchannels * 4
            if decoded > max_bytes:
                return unknown
            wanted = [
                i
                for i, name in enumerate(names)
                if ".Combined." in name or "Debug Sample Count" in name
            ]
            if wanted:
                data = inp.read_image(index, 0, 0, spec.nchannels, oiio.FLOAT)
                if data is None:
                    return unknown
                for i in wanted:
                    channels[names[i]] = np.asarray(data)[..., i].copy()
            index += 1
    finally:
        inp.close()
    count_name = next((n for n in channels if n.endswith("Debug Sample Count.X")), None)
    if count_name is None:
        return {**unknown, "subimages": subimages}
    layer = count_name.removesuffix("Debug Sample Count.X")
    rgba_names = [f"{layer}Combined.{c}" for c in "RGBA"]
    if not all(n in channels for n in rgba_names):
        return {**unknown, "subimages": subimages}
    rgba = np.stack([channels[n] for n in rgba_names], axis=-1)
    result = summarize(channels[count_name], rgba, cap)
    result.update(subimages=subimages, exr_sha256=sha256(path), bytes=path.stat().st_size)
    return result
