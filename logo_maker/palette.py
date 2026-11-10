"""Color facts the pipeline computes itself; jev only judges what needs taste.

`extract_colors` finds candidate brand colors in a reference image, jev judges
each one, and `contrast` / `wcag_problems` enforce WCAG 2.1 ratios in code.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from coloraide import Color
from PIL import Image as _PILImage

HEX = re.compile(r"^#[0-9A-F]{6}$")

#: Contrast floors: text-ish roles need 4.5:1, accents need 3:1 (WCAG 2.1 AA).
TEXT_ROLES = ("ink", "primary")
ACCENT_ROLES = ("accent",)
TEXT_MIN = 4.5
ACCENT_MIN = 3.0


def normalize(hexcode: str) -> str:
    """Any common hex spelling to uppercase `#RRGGBB`; raises `ValueError` otherwise."""
    text = hexcode.strip().lstrip("#")
    if len(text) == 3 and all(c in "0123456789abcdefABCDEF" for c in text):
        text = "".join(c * 2 for c in text)
    result = f"#{text.upper()}"
    if not HEX.match(result):
        raise ValueError(f"{hexcode!r} is not a hex color")
    return result


def extract_colors(image: Path, n: int = 8) -> list[tuple[str, float]]:
    """Top `n` opaque colors as (hex, pixel share); transparent pixels are ignored."""
    im = _PILImage.open(image).convert("RGBA")
    flat: Any = im.get_flattened_data()
    px = [(r, g, b) for r, g, b, a in flat if a >= 128]
    if not px:
        return []
    solid = _PILImage.new("RGB", (len(px), 1))
    solid.putdata(px)
    quant = solid.quantize(colors=n, method=_PILImage.Quantize.MEDIANCUT)
    counts = quant.getcolors(len(px))
    if not counts:
        return []
    palette = quant.getpalette() or []
    total = len(px)
    out = []
    for count, index in sorted(counts, reverse=True):
        if not isinstance(index, int):
            continue  # RGB-mode tables key pixels by tuple; quantized art uses indices
        r, g, b = palette[3 * index : 3 * index + 3]
        out.append((f"#{r:02X}{g:02X}{b:02X}", count / total))
    return out


def contrast(a: str, b: str) -> float:
    """WCAG 2.1 contrast ratio between two hex colors (1.0 to 21.0)."""
    return Color(normalize(a)).contrast(normalize(b))


def wcag_problems(palette: dict[str, str]) -> list[str]:
    """Human-readable WCAG failures; roles the palette lacks are skipped, not failed."""
    problems = []
    background = palette.get("background")
    if background is None:
        return ["palette has no background role to check against"]
    for role in TEXT_ROLES:
        if role in palette:
            ratio = contrast(palette[role], background)
            if ratio < TEXT_MIN:
                problems.append(f"{role} on background is {ratio:.2f}:1, needs >={TEXT_MIN}:1")
    for role in ACCENT_ROLES:
        if role in palette:
            ratio = contrast(palette[role], background)
            if ratio < ACCENT_MIN:
                problems.append(f"{role} on background is {ratio:.2f}:1, needs >={ACCENT_MIN}:1")
    return problems
