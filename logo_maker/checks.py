"""Code QA for renders: veil/haze, margins, palette presence, edge aliasing.

Pure functions over PNG files (no jev). Thresholds live here as module
constants so the QA loop and tests reference one documented source.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

# A pixel counts as object body (as opposed to haze, glow, or shadow).
SOLID_ALPHA = 64
# Alpha at or below this counts as haze-level: nearly invisible, but enough
# to dirty a "transparent" background when composited or converted.
VEIL_ALPHA_MAX = 16
# Fraction of the open background (outside the object body plus a halo zone)
# covered in haze-level alpha that reads as a veil rather than stray pixels.
VEIL_HAZE_FRACTION = 0.02
# A pixel counts as occupied when measuring margins and bboxes.
OBJECT_ALPHA = 8
# Alpha band edges: below EDGE_LO is background, above EDGE_HI is solid.
EDGE_LO = 16
EDGE_HI = 235
# A neighboring-pixel alpha jump bigger than this is a hard (unfiltered) step.
HARD_JUMP = 200
# Edges read as aliased when more than this fraction of boundary transitions
# are hard jumps instead of graded steps.
ALIASED_FRACTION = 0.5
# A palette role reads as present when a dominant render color lands within
# this deltaE2000 distance of it.
PRESENT_DE_MAX = 12.0
# How many dominant colors color_report extracts.
N_DOMINANT = 5


def _veil_exclude_px(width: int) -> int:
    """Halo zone around the body ignored by alpha_report.

    Resampling kernels legitimately spread a faint halo a few pixels past
    the edge; a real veil covers far more than this zone.
    """
    return max(4, width // 250)


def _alpha(png: Path) -> tuple[np.ndarray, tuple[int, int]]:
    """Alpha channel as uint8 (h, w) plus (width, height)."""
    with Image.open(png) as im:
        rgba = im.convert("RGBA")
    arr = np.asarray(rgba)
    return arr[:, :, 3], (rgba.width, rgba.height)


def open_background(alpha: np.ndarray) -> np.ndarray:
    """Pixels outside the object body (alpha >= SOLID_ALPHA) and its halo zone.

    Anti-aliased edges, soft shadows hugging the mark, and resampling halos sit
    inside the halo zone; everything past it is open background. With no body,
    the whole frame is open background.
    """
    solid = alpha >= SOLID_ALPHA
    if not solid.any():
        return np.ones_like(solid)
    d = _veil_exclude_px(alpha.shape[1])
    grown = Image.fromarray(solid).filter(ImageFilter.MaxFilter(2 * d + 1))
    return ~np.asarray(grown, dtype=bool)


def alpha_report(png: Path) -> dict:
    """Check the open background (see `open_background`) for a veil: faint
    non-zero alpha spread wide."""
    alpha, _size = _alpha(png)
    solid = alpha >= SOLID_ALPHA
    bbox = None
    if solid.any():
        ys, xs = np.nonzero(solid)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    bg = alpha[open_background(alpha)]
    if bg.size == 0:
        return {"veil": False, "haze_fraction": 0.0, "min_bg_alpha": 0, "bbox": bbox}
    haze_fraction = float(((bg > 0) & (bg <= VEIL_ALPHA_MAX)).mean())
    return {
        "veil": bool(haze_fraction > VEIL_HAZE_FRACTION),
        "haze_fraction": haze_fraction,
        "min_bg_alpha": int(bg.min()),
        "bbox": bbox,
    }


def margin_report(png: Path, *, min_margin: float = 0.04) -> dict:
    """Check the object bbox against the frame; touching the frame reads cut off."""
    alpha, (width, height) = _alpha(png)
    occupied = alpha >= OBJECT_ALPHA
    if not occupied.any():
        return {
            "bbox": None,
            "margins": {"left": 1.0, "top": 1.0, "right": 1.0, "bottom": 1.0},
            "min_margin": min_margin,
            "cut_off": False,
            "touching": False,
            "empty": True,
        }
    ys, xs = np.nonzero(occupied)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    margins = {
        "left": x0 / width,
        "top": y0 / height,
        "right": (width - x1) / width,
        "bottom": (height - y1) / height,
    }
    return {
        "bbox": [x0, y0, x1, y1],
        "margins": margins,
        "min_margin": min_margin,
        "cut_off": bool(any(m < min_margin for m in margins.values())),
        "touching": bool(any(m == 0 for m in margins.values())),
        "empty": False,
    }


def _dominant(opaque: np.ndarray, n: int = N_DOMINANT) -> list[tuple[str, float]]:
    """Top color bins (4 bits/channel) with pixel fractions, as (#RRGGBB, fraction)."""
    packed = (
        (opaque[:, 0].astype(np.uint32) >> 4 << 8)
        | (opaque[:, 1].astype(np.uint32) >> 4 << 4)
        | (opaque[:, 2].astype(np.uint32) >> 4)
    )
    keys, counts = np.unique(packed, return_counts=True)
    order = np.argsort(counts)[::-1][:n]
    total = float(counts.sum())
    out = []
    for idx in order:
        key = int(keys[idx])
        rgb = ((key >> 8) & 0xF) * 17, ((key >> 4) & 0xF) * 17, (key & 0xF) * 17
        out.append((f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}", float(counts[idx]) / total))
    return out


def color_report(png: Path, palette: dict[str, str]) -> dict:
    """Which palette roles appear among the render's dominant opaque colors.

    Dominant colors are compared in OKLab; distance is deltaE2000 via
    coloraide (which converts to Lab internally for the 2000 formula).
    """
    from coloraide import Color  # lazy: 27 ms, and export workers never compare colors

    with Image.open(png) as im:
        rgba = np.asarray(im.convert("RGBA"))
    opaque = rgba[rgba[:, :, 3] >= 128][:, :3]
    if opaque.shape[0] < 100:
        return {"dominant": [], "roles_present": [], "empty": True}
    roles = {role: Color(hexval).convert("oklab") for role, hexval in palette.items()}
    dominant = []
    present: set[str] = set()
    for hexval, fraction in _dominant(opaque):
        sample = Color(hexval).convert("oklab")
        distances = {role: float(sample.delta_e(ref, method="2000")) for role, ref in roles.items()}
        nearest = min(distances, key=lambda role: distances[role])
        if distances[nearest] <= PRESENT_DE_MAX:
            present.add(nearest)
        dominant.append(
            {
                "hex": hexval,
                "fraction": fraction,
                "nearest_role": nearest,
                "distance": distances[nearest],
            }
        )
    return {"dominant": dominant, "roles_present": sorted(present), "empty": False}


def edge_report(png: Path) -> dict:
    """Stair-step metric on the alpha edge: hard jumps vs graded steps.

    A clean (anti-aliased or filtered) edge moves from background to solid
    through intermediate alpha values, so neighboring-pixel transitions are
    small. An aliased edge jumps straight from ~0 to ~255. The metric is the
    fraction of boundary transitions that are hard jumps.
    """
    alpha, _ = _alpha(png)
    band = (alpha >= EDGE_LO) & (alpha <= EDGE_HI)
    hard = smooth = 0
    for a, b in ((alpha[:, 1:], alpha[:, :-1]), (alpha[1:, :], alpha[:-1, :])):
        delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
        hard += int((delta > HARD_JUMP).sum())
        # A smooth step touches the mid band on exactly one side without jumping far.
        a_mid = (a >= EDGE_LO) & (a <= EDGE_HI)
        b_mid = (b >= EDGE_LO) & (b <= EDGE_HI)
        smooth += int(((a_mid ^ b_mid) & (delta <= HARD_JUMP)).sum())
    total = hard + smooth
    aliasing = (hard / total) if total else 0.0
    return {
        "edge_pixels": int(band.sum()),
        "hard_jumps": hard,
        "smooth_steps": smooth,
        "aliasing": aliasing,
        "aliased": bool(aliasing > ALIASED_FRACTION),
    }
