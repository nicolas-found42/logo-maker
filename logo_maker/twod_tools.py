"""2D generative tools: each function returns SVG path data a Motif can add.

Every function is backed by a real tool (never a mock): rough.js, perfect-freehand,
d3-delaunay, trianglify, heerich, the Go ``primitive`` binary, vpype, and FontForge.
Single-shape tools return one :class:`Shape`; field tools (voronoi, low-poly,
voxels, primitive) return one Shape per cell. All coordinates are y-down SVG px;
use :func:`logo_maker.motif.fit` to land them in the radius-470 circle.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from logo_maker.motif import HEX_RE, Motif, MotifError, parse_d, stroke_d, svg_root, svg_root_text
from logo_maker.proc import ToolError, node, require, run

INK = "#1A1A1A"  # neutral default fill; the caller recolors through Motif.add
GRAYS = ("#1A1A1A", "#404040", "#6E6E6E", "#9A9A9A", "#C8C8C8")


@dataclass(frozen=True)
class Shape:
    """One fill-ready SVG path: ``d`` holds absolute coordinates, no transforms, no strokes."""

    d: str
    fill: str = INK


def _check_fill(fill: str) -> str:
    if not HEX_RE.match(fill):
        raise MotifError(f"bad fill {fill!r}; want #RRGGBB")
    return fill.upper()


def _close(d: str) -> str:
    d = d.strip()
    return d if d.endswith(("Z", "z")) else d + " Z"


def sketchy(
    d: str,
    *,
    roughness: float = 1.5,
    bowing: float = 1.0,
    seed: int = 0,
    width: float = 5.0,
    fill: str = INK,
) -> list[Shape]:
    """A hand-drawn wobble of a path via rough.js; the outline is stroked to a fill.

    Returns the stroked sketchy outline plus the sketchy solid fill underneath.
    """
    fill = _check_fill(fill)
    out = node(
        "rough",
        {
            "d": Motif.path(d),
            "seed": seed,
            "roughness": roughness,
            "bowing": bowing,
            "fill": fill,
            "fillStyle": "solid",
        },
    )
    shapes = []
    for s in out.get("sets", []):
        if s["kind"] == "stroke":
            shapes.append(Shape(stroke_d(_close(s["d"]), width), fill))
        else:
            shapes.append(Shape(Motif.path(_close(s["d"])), fill))
    if not shapes:
        raise ToolError("rough.mjs returned no sets")
    return shapes


def freehand(
    points_with_pressure: list,
    *,
    size: float = 16,
    thinning: float = 0.5,
    smoothing: float = 0.5,
    fill: str = INK,
) -> list[Shape]:
    """A pressure-sensitive stroke outline via perfect-freehand.

    ``points_with_pressure`` is ``[(x, y), ...]`` or ``[(x, y, pressure), ...]``.
    """
    fill = _check_fill(fill)
    pts = [
        [float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.5] for p in points_with_pressure
    ]
    if len(pts) < 2:
        raise MotifError("freehand needs 2+ points")
    out = node(
        "freehand", {"points": pts, "size": size, "thinning": thinning, "smoothing": smoothing}
    )
    return [Shape(Motif.polygon(out["outline"]), fill)]


def _cells(kind: str, points, bounds, palette: list[str] | None) -> list[Shape]:
    pts = [[float(p[0]), float(p[1])] for p in points]
    if len(pts) < 3:
        raise MotifError(f"{kind} needs 3+ points")
    box = [0.0, 0.0, 1000.0, 1000.0] if bounds is None else [float(v) for v in bounds]
    out = node("delaunay", {"points": pts, "bounds": box, "kind": kind})
    pals = [_check_fill(c) for c in palette] if palette else list(GRAYS)
    return [Shape(Motif.polygon(cell), pals[i % len(pals)]) for i, cell in enumerate(out["cells"])]


def voronoi(points, bounds=None, *, palette: list[str] | None = None) -> list[Shape]:
    """Voronoi cells of points clipped to bounds (default the 1000x1000 box), via d3-delaunay."""
    return _cells("voronoi", points, bounds, palette)


def delaunay(points, bounds=None, *, palette: list[str] | None = None) -> list[Shape]:
    """Delaunay triangles of points via d3-delaunay (bounds only clips nothing; kept for symmetry)."""
    return _cells("delaunay", points, bounds, palette)


def low_poly(
    width: float,
    height: float,
    *,
    cell_size: float = 48,
    variance: float = 0.75,
    seed: int = 0,
    palette: list[str] | None = None,
) -> list[Shape]:
    """A trianglify triangle field, built from the pattern's points/polys data (no DOM)."""
    payload: dict = {
        "width": width,
        "height": height,
        "cellSize": cell_size,
        "variance": variance,
        "seed": str(seed),
    }
    if palette is not None:
        payload["xColors"] = [_check_fill(c) for c in palette]
    out = node("trianglify", payload)
    shapes = [Shape(Motif.polygon(t["pts"]), _check_fill(t["fill"])) for t in out["triangles"]]
    if not shapes:
        raise ToolError("trianglify.mjs returned no triangles")
    return shapes


def voxels(
    spec: dict, *, tile: float = 24, fill: str | None = None, palette: list[str] | None = None
) -> list[Shape]:
    """A heerich voxel scene rendered to SVG polygons (strokes dropped, fills kept).

    ``spec`` maps to heerich geometry: ``{"cells": [[x,y,z], ...]}`` for unit
    boxes, ``{"box": [w,h,d]}``, ``{"sphere": {"center": [...], "radius": r}}``,
    or ``{"ops": [...]}`` for full control (each op is one heerich
    ``applyGeometry`` argument; ``"test"`` may be ``"ball:..."``-style named tests).
    """
    ops: list[dict] = []
    if "ops" in spec:
        ops = list(spec["ops"])
    elif "cells" in spec:
        ops = [
            {"type": "box", "position": [int(c[0]), int(c[1]), int(c[2])], "size": [1, 1, 1]}
            for c in spec["cells"]
        ]
    elif "box" in spec:
        ops = [{"type": "box", "position": [0, 0, 0], "size": list(spec["box"])}]
    elif "sphere" in spec:
        ops = [
            {
                "type": "sphere",
                "center": list(spec["sphere"]["center"]),
                "radius": spec["sphere"]["radius"],
            }
        ]
    else:
        raise MotifError("voxels spec needs one of cells, box, sphere, ops")
    if not ops:
        raise MotifError("voxels spec holds no geometry")
    out = node("heerich", {"tile": tile, "ops": ops, "smooth": bool(spec.get("smooth", False))})
    return _heerich_shapes(out["svg"], fill, palette)


def _heerich_shapes(svg: str, fill: str | None, palette: list[str] | None) -> list[Shape]:
    root = svg_root_text(svg)
    if fill is not None:
        fill = _check_fill(fill)
    pals = [_check_fill(c) for c in palette] if palette else None
    order: dict[str, int] = {}
    shapes = []
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] not in ("polygon", "path"):
            continue
        if "points" in el.attrib:
            d = "M" + el.attrib["points"].strip().replace(" ", " L") + " Z"
        elif el.get("d"):
            d = el.get("d", "")
        else:
            continue
        try:
            Motif.path(d)
        except MotifError:
            continue
        if fill is not None:
            color = fill
        elif pals is not None:
            key = el.get("data-voxel", str(len(order)))
            order.setdefault(key, len(order))
            color = pals[order[key] % len(pals)]
        else:
            color = el.get("fill", INK)
            color = color.upper() if HEX_RE.match(color) else INK
        shapes.append(Shape(d, color))
    if not shapes:
        raise ToolError("heerich.mjs returned no polygons")
    return shapes


def primitive_abstract(image: Path | str, *, shapes: int = 64, mode: int = 1) -> list[Shape]:
    """A geometric abstraction of an image via the Go ``primitive`` binary.

    ``mode``: 0 combo, 1 triangle, 2 rect, 3 ellipse, 4 circle, 5 rotated rect,
    6 beziers, 7 rotated ellipse, 8 polygon. primitive picks its own randomness,
    so repeated runs differ; the first shape is usually the background rect.
    """
    if not 0 <= mode <= 8:
        raise MotifError(f"bad primitive mode {mode}; want 0-8")
    if shapes < 1:
        raise MotifError(f"bad primitive shapes={shapes}; want 1+")
    image = Path(image)
    if not image.is_file():
        raise MotifError(f"no image at {image}")
    binary = shutil.which("primitive") or os.path.join(os.path.expanduser("~/go/bin"), "primitive")
    if not shutil.which(binary) and not Path(binary).is_file():
        require(
            "primitive",
            "go install github.com/fogleman/primitive@latest and add $(go env GOPATH)/bin to PATH",
        )
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "prim.svg"
        run(
            [
                binary,
                "-i",
                str(image),
                "-o",
                str(out),
                "-n",
                str(shapes),
                "-m",
                str(mode),
                "-r",
                "256",
            ],
            timeout=600,
        )
        return _primitive_shapes(out.read_text())


def _primitive_color(el: ET.Element) -> str:
    color = (el.get("fill") or "#000000").strip()
    if not HEX_RE.match(color):
        return INK
    try:
        alpha = float(el.get("fill-opacity", "1"))
    except ValueError:
        alpha = 1.0
    if alpha >= 1:
        return color.upper()
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))

    def mix(v: float) -> int:
        return round(v * alpha + 255 * (1 - alpha))

    return f"#{mix(r):02X}{mix(g):02X}{mix(b):02X}"


def _primitive_shapes(svg: str) -> list[Shape]:
    root = svg_root_text(svg)
    shapes = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        color = _primitive_color(el)
        try:
            if tag == "path" and el.get("d"):
                shapes.append(Shape(Motif.path(el.get("d", "")), color))
            elif tag == "polygon" and el.get("points"):
                pts = [tuple(map(float, p.split(","))) for p in el.get("points", "").split()]
                shapes.append(Shape(Motif.polygon(pts), color))
            elif tag == "rect":
                shapes.append(
                    Shape(
                        Motif.rect(
                            float(el.get("x", 0)),
                            float(el.get("y", 0)),
                            float(el.get("width", 0)),
                            float(el.get("height", 0)),
                            float(el.get("rx", 0) or 0),
                        ),
                        color,
                    )
                )
            elif tag == "circle":
                shapes.append(
                    Shape(
                        Motif.circle(
                            float(el.get("cx", 0)), float(el.get("cy", 0)), float(el.get("r", 0))
                        ),
                        color,
                    )
                )
            elif tag == "ellipse":
                cx, cy = float(el.get("cx", 0)), float(el.get("cy", 0))
                rx, ry = float(el.get("rx", 0)), float(el.get("ry", 0))
                k = 0.5522847498307936
                shapes.append(
                    Shape(
                        Motif.path(
                            f"M{cx + rx} {cy} C{cx + rx} {cy + k * ry} {cx + k * rx} {cy + ry} {cx} {cy + ry} "
                            f"C{cx - k * rx} {cy + ry} {cx - rx} {cy + k * ry} {cx - rx} {cy} "
                            f"C{cx - rx} {cy - k * ry} {cx - k * rx} {cy - ry} {cx} {cy - ry} "
                            f"C{cx + k * rx} {cy - ry} {cx + rx} {cy - k * ry} {cx + rx} {cy} Z"
                        ),
                        color,
                    )
                )
        except (MotifError, ValueError, TypeError):
            continue
    if not shapes:
        raise ToolError("primitive produced no convertible shapes")
    return shapes


def _vpype_cmd() -> list[str]:
    local = Path(sys.executable).parent / "vpype"
    if local.is_file():
        return [str(local)]
    if shutil.which("vpype"):
        return ["vpype"]
    raise ToolError("vpype not found; fix: just setup (it ships with logo-maker)")


def plotter_lines(
    paths: list[str], *, width: float = 3.0, epsilon: float = 1.0, fill: str = INK
) -> list[Shape]:
    """Merge and simplify centerlines with vpype, then outline them to fills.

    ``epsilon`` is the simplify tolerance in px. Line art comes back as thin
    fills because the motif contract forbids strokes.
    """
    fill = _check_fill(fill)
    if not paths:
        raise MotifError("plotter_lines needs 1+ paths")
    for d in paths:
        Motif.path(d)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.svg"
        dst = Path(tmp) / "out.svg"
        body = "".join(f'<path d="{d}" fill="none" stroke="black"/>' for d in paths)
        src.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000">{body}</svg>'
        )
        mm = epsilon * 25.4 / 96  # vpype lengths are mm; the artwork is px at 96 dpi
        run(
            [
                *_vpype_cmd(),
                "read",
                str(src),
                "linemerge",
                "--tolerance",
                f"{mm}",
                "linesimplify",
                "--tolerance",
                f"{mm}",
                "write",
                str(dst),
            ],
            timeout=120,
        )
        root = svg_root(dst)
        out = []
        for d in _svg_centerlines(root):
            try:
                out.append(Shape(stroke_d(d, width), fill))
            except MotifError:
                continue
    if not out:
        raise ToolError("vpype returned no lines")
    return out


def _svg_centerlines(root: ET.Element) -> list[str]:
    """vpype's writer emits line/polygon/polyline/path; all become centerline d strings."""
    ds = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        try:
            if tag == "path" and el.get("d"):
                ds.append(Motif.path(el.get("d", "")))
            elif tag == "line":
                ds.append(
                    f"M{el.get('x1', 0)} {el.get('y1', 0)} L{el.get('x2', 0)} {el.get('y2', 0)}"
                )
            elif tag in ("polygon", "polyline") and el.get("points"):
                pts = [tuple(map(float, p.split(","))) for p in el.get("points", "").split()]
                ds.append(Motif.polygon(pts) if tag == "polygon" else Motif._polyline(pts))
        except (MotifError, ValueError, TypeError):
            continue
    return ds


def fontforge_glyphs(font_path: Path | str, script_ops: list[dict]) -> list[Shape]:
    """Build glyphs in FontForge and export their outlines (e.g. a ligature of two glyphs).

    ``script_ops`` run in order against one temp glyph namespace:
    ``{"new": name}`` creates a glyph, ``{"clear": name}`` empties it,
    ``{"add": {"from": src, "into": dst, "dx": 0, "dy": 0}}`` appends ``src``'s
    outlines into ``dst`` shifted by ``(dx, dy)`` (via a scratch glyph, so
    earlier content never moves), ``{"advance": {"glyph": name, "width": w}}``
    sets the advance. Returns y-down outlines in font units (baseline y=0).
    """
    if not script_ops:
        raise MotifError("fontforge_glyphs needs 1+ script_ops")
    script = _fontforge_script(font_path, script_ops)
    with tempfile.TemporaryDirectory() as tmp:
        job = Path(tmp) / "job.py"
        job.write_text(script)
        require("fontforge", "brew install fontforge")
        proc = run(["fontforge", "-script", str(job)], timeout=300)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        raise ToolError(f"fontforge printed nothing; stderr: {proc.stderr.strip()[-800:]}")
    try:
        import json

        data = json.loads(lines[-1])
    except ValueError as exc:
        raise ToolError(f"fontforge printed no JSON: {lines[-1][:200]}") from exc
    if not data:
        raise ToolError("fontforge exported no glyph outlines")
    return [Shape(Motif.path(_flip_y(d)), INK) for d in data.values()]


def _flip_y(d: str) -> str:
    from logo_maker.motif import segments_to_d

    return segments_to_d([(v, [(x, -y) for x, y in pts]) for v, pts in parse_d(d)])


def _fontforge_script(font_path: Path | str, ops: list[dict]) -> str:
    targets: list[str] = []
    lines = [
        "import fontforge, json",
        f"font = fontforge.open({str(font_path)!r})",
        "scratch = 'uniE000_private_scratch'",
        "try:\n    font.createChar(-1, scratch)\nexcept Exception:\n    pass",
    ]
    for op in ops:
        if "new" in op:
            name = op["new"]
            targets.append(name)
            lines.append(f"font.createChar(-1, {name!r})")
        elif "clear" in op:
            lines.append(f"font.selection.select({op['clear']!r}); font.clear()")
        elif "add" in op:
            spec = op["add"]
            src, dst = spec["from"], spec["into"]
            dx, dy = float(spec.get("dx", 0)), float(spec.get("dy", 0))
            if dst not in targets:
                targets.append(dst)
            lines.append(
                f"font.selection.select({src!r}); font.copy()\n"
                "font.selection.select(scratch); font.clear(); font.paste()\n"
                f"font.selection.select(scratch); font.transform((1,0,0,1,{dx},{dy}))\n"
                "font.selection.select(scratch); font.copy()\n"
                f"try:\n    font.createChar(-1, {dst!r})\n"
                "except Exception:\n    pass\n"
                f"font.selection.select({dst!r}); font.paste()"
            )
        elif "advance" in op:
            spec = op["advance"]
            lines.append(f"font[{spec['glyph']!r}].width = {int(spec['width'])}")
        else:
            raise MotifError(f"bad fontforge op {op!r}; want new/clear/add/advance")
    lines.append(
        "out = {}\n"
        "for _name in " + repr(targets) + ":\n"
        "    _g = font[_name]\n"
        "    _parts = []\n"
        "    for _c in _g.foreground:\n"
        "        _pts = [(p.x, p.y, p.on_curve) for p in _c]\n"
        "        if _pts:\n"
        "            _parts.append(_dump(_pts))\n"
        "    out[_name] = ' '.join(_parts)\n"
        "print(json.dumps(out))"
    )
    dump = """
def _dump(pts):
    pts = list(pts)
    if pts[0][2] == 0:
        if pts[-1][2] == 1:
            pts = pts[-1:] + pts[:-1]
        else:
            mx, my = (pts[-1][0] + pts[0][0]) / 2, (pts[-1][1] + pts[0][1]) / 2
            pts = [(mx, my, 1)] + pts
    d = ["M%s %s" % (pts[0][0], pts[0][1])]
    n = len(pts)
    i = 1
    while i < n:
        x, y, on = pts[i]
        if on:
            d.append("L%s %s" % (x, y))
            i += 1
        else:
            nx, ny, non = pts[(i + 1) % n]
            if non:
                d.append("Q%s %s %s %s" % (x, y, nx, ny))
                i += 2
            else:
                mx, my = (x + nx) / 2, (y + ny) / 2
                d.append("Q%s %s %s %s" % (x, y, mx, my))
                i += 1
    d.append("Z")
    return " ".join(d)
"""
    return dump + "\n".join(lines) + "\n"
