"""Trace raster references into SVG paths with vtracer (geometry use only).

A reference marked ``use='geometry'`` in brief.toml is artwork the brief owner
made or licensed, so the tool may derive shapes from it. ``use='style'`` means
look-but-don't-trace: jev reads its style, and tracing raises. The traced paths
still need :func:`logo_maker.motif.fit` before they satisfy the motif contract.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import vtracer
from PIL import Image

from logo_maker.motif import HEX_RE, svg_root_text

__all__ = ["TraceError", "shapes", "trace"]


class TraceError(ValueError):
    """The reference may not be traced, or the image cannot be read."""


def trace(image: Path, *, colors: int = 8, mode: str = "geometry") -> str:
    """Trace an image to an SVG string. ``mode`` is the reference's ``use`` field.

    Raises TraceError for ``mode='style'``. ``colors`` above 2 traces in color,
    otherwise binary. vtracer emits ``translate`` wrappers, which are baked into
    the path data so the output stays transform-free.
    """
    if mode != "geometry":
        raise TraceError(
            f"reference is marked use={mode!r}: jev may read its style, but the tool "
            "must not trace its shapes (only use='geometry' art may be traced)"
        )
    if colors < 2:
        raise TraceError(f"colors={colors}: want 2+")
    image = Path(image)
    if not image.is_file():
        raise TraceError(f"no image at {image}")
    try:
        img = Image.open(image).convert("RGBA")
    except OSError as exc:
        raise TraceError(f"cannot read {image}: {exc}") from exc
    raw = img.tobytes()
    pixels = [(raw[i], raw[i + 1], raw[i + 2], raw[i + 3]) for i in range(0, len(raw), 4)]
    svg = vtracer.convert_pixels_to_svg(
        pixels,
        (img.width, img.height),
        colormode="color" if colors > 2 else "binary",
        hierarchical="stacked",
        mode="spline",
    )
    return _bake_transforms(svg if isinstance(svg, str) else svg.decode())


def _bake_transforms(svg: str) -> str:
    """Inline translate transforms into path data; drop empty ones."""
    root = svg_root_text(svg)
    for el in root.iter():
        tr = (el.get("transform") or "").strip()
        if not tr:
            continue
        match = re.fullmatch(r"translate\(\s*([-\d.]+)[,\s]+([-\d.]+)\s*\)", tr)
        if tr in ("translate(0,0)", "translate(0, 0)"):
            el.attrib.pop("transform", None)
        elif match is not None:
            targets = [el] if el.tag.rsplit("}", 1)[-1] == "path" else list(el.iter())
            dx, dy = float(match.group(1)), float(match.group(2))
            for path in targets:
                if path.tag.rsplit("}", 1)[-1] == "path" and path.get("d"):
                    path.set("d", _shift(path.get("d", ""), dx, dy))
            del el.attrib["transform"]
        else:
            raise TraceError(f"traced SVG has an unsupported transform {tr!r}")
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    return ET.tostring(root, encoding="unicode")


def _shift(d: str, dx: float, dy: float) -> str:
    from logo_maker.motif import parse_d, segments_to_d

    return segments_to_d([(v, [(x + dx, y + dy) for x, y in pts]) for v, pts in parse_d(d)])


def shapes(svg: str) -> list[tuple[str, str]]:
    """An traced SVG string to ``(d, fill)`` pairs (fills default to black)."""
    root = svg_root_text(svg)
    out = []
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] != "path" or not el.get("d"):
            continue
        fill = (el.get("fill") or "#000000").strip()
        out.append((el.get("d", ""), fill.upper() if HEX_RE.match(fill) else "#000000"))
    return out
