"""The 2D motif master: authoring API for agent-written motif.py files, plus derived formats.

``concepts/<slug>/motif.svg`` is the single source of 2D geometry: only
``<path>`` elements, absolute coordinates, no transforms, no strokes, every path
with a unique id, a ``#RRGGBB`` fill, and optional ``data-role`` /
``data-height`` / ``data-layer`` attributes. The mark fits in a centered circle
of radius 470 in a 1000x1000 y-down box.

``motif.json`` is derived by :func:`flatten` (overlaps removed with
skia-pathops, curves flattened at 12 steps, holes kept as separate contours
under even-odd fill). Everything 3D or flat is built from these two files, so
flat and relief always match.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

import drawsvg as dw
import pathops
import resvg_py
from PIL import Image, ImageDraw

from logo_maker.paths import REPO_ROOT

VIEWBOX = 1000.0
CX = CY = 500.0
RADIUS = 470.0
GEOM_TOL = 1.0
FLATTEN_STEPS = 12
ROLES = ("primary", "secondary", "accent", "highlight", "ink")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

__all__ = [
    "CX",
    "CY",
    "FLATTEN_STEPS",
    "GEOM_TOL",
    "RADIUS",
    "ROLES",
    "VIEWBOX",
    "Motif",
    "MotifError",
    "bbox_of_d",
    "difference",
    "fit",
    "flatten",
    "flatten_d",
    "intersection",
    "mono",
    "parse_d",
    "poly_area",
    "rasterize",
    "run_motif_script",
    "silhouette",
    "size_sheet",
    "stroke_d",
    "transform_d",
    "union",
    "validate",
    "xor",
]


class MotifError(ValueError):
    """A motif breaks the contract, or a motif script failed."""


# ----------------------------------------------------------------------------
# Path data: parse, serialize, transform, flatten
# ----------------------------------------------------------------------------

# A segment is (verb, points): M/L with 1 point, C with 3, Q with 2, Z with none.
Segment = tuple[str, list[tuple[float, float]]]

_TOKEN_RE = re.compile(r"[A-Za-z]|-?\d*\.?\d+(?:[eE][-+]?\d+)?|-?\.\d+(?:[eE][-+]?\d+)?")


def _tokens(d: str) -> list[str]:
    return _TOKEN_RE.findall(d)


def _arc_to_beziers(
    x0: float,
    y0: float,
    rx: float,
    ry: float,
    rot: float,
    large: float,
    sweep: float,
    x1: float,
    y1: float,
) -> list[Segment]:
    """SVG endpoint arcs as cubic segments (W3C implementation notes, F.6.5)."""
    if rx == 0 or ry == 0:
        return [("L", [(x1, y1)])]
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(rot % 360)
    dx, dy = (x0 - x1) / 2, (y0 - y1) / 2
    x1p = math.cos(phi) * dx + math.sin(phi) * dy
    y1p = -math.sin(phi) * dx + math.cos(phi) * dy
    lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        co = -co
    cxp = co * rx * y1p / ry
    cyp = -co * ry * x1p / rx
    cx = math.cos(phi) * cxp - math.sin(phi) * cyp + (x0 + x1) / 2
    cy = math.sin(phi) * cxp + math.cos(phi) * cyp + (y0 + y1) / 2

    def angle(ux: float, uy: float, vx: float, vy: float) -> float:
        dot = ux * vx + uy * vy
        det = ux * vy - uy * vx
        return math.atan2(det, dot)

    t1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    if sweep and dt < 0:
        dt += 2 * math.pi
    n = max(1, math.ceil(abs(dt) / (math.pi / 2)))
    out: list[Segment] = []
    for i in range(n):
        a0, a1 = t1 + dt * i / n, t1 + dt * (i + 1) / n
        alpha = 4 / 3 * math.tan((a1 - a0) / 4)

        def pt(t: float) -> tuple[float, float]:
            ex, ey = rx * math.cos(t), ry * math.sin(t)
            return (
                math.cos(phi) * ex - math.sin(phi) * ey + cx,
                math.sin(phi) * ex + math.cos(phi) * ey + cy,
            )

        p0, p3 = pt(a0), pt(a1)

        def off(t: float) -> tuple[float, float]:
            dex, dey = -rx * math.sin(t), ry * math.cos(t)
            return (
                math.cos(phi) * dex - math.sin(phi) * dey,
                math.sin(phi) * dex + math.cos(phi) * dey,
            )

        d0, d1 = off(a0), off(a1)
        out.append(
            (
                "C",
                [
                    (p0[0] + alpha * d0[0], p0[1] + alpha * d0[1]),
                    (p3[0] - alpha * d1[0], p3[1] - alpha * d1[1]),
                    p3,
                ],
            )
        )
    return out


def parse_d(d: str) -> list[Segment]:
    """Parse SVG path data to absolute segments (M/L/C/Q/Z). Arcs become cubics.

    Relative commands are rejected: the motif contract needs absolute coordinates.
    """
    toks = _tokens(d)
    segs: list[Segment] = []
    i = 0
    cmd: str | None = None
    x = y = 0.0
    sub0 = (0.0, 0.0)
    last_cubic = None  # last cubic control point, for S reflection
    last_q = None  # last quadratic control point, for T reflection

    def num() -> float:
        nonlocal i
        if i >= len(toks) or toks[i] in "AaCcHhLlMmQqSsTtVvZz":
            raise MotifError(
                f"bad path data: expected a number near {toks[max(0, i - 3) : i + 2]!r}"
            )
        v = float(toks[i])
        i += 1
        return v

    while i < len(toks):
        tok = toks[i]
        if len(tok) == 1 and tok in "AaCcHhLlMmQqSsTtVvZz":
            if tok != tok.upper():
                raise MotifError(
                    f"bad path data: relative command {tok!r}; use absolute coordinates"
                )
            cmd = tok
            i += 1
            if cmd == "Z":
                x, y = sub0
                segs.append(("Z", []))
                last_cubic = last_q = None
                cmd = None
                continue
        elif len(tok) == 1 and tok.isalpha():
            raise MotifError(f"bad path data: unknown command {tok!r}")
        elif cmd is None:
            raise MotifError(f"bad path data: {tok!r} with no command")
        if cmd == "M":
            x, y = num(), num()
            sub0 = (x, y)
            segs.append(("M", [(x, y)]))
            last_cubic = last_q = None
            cmd = "L"  # further pairs are implicit linetos
        elif cmd == "L":
            x, y = num(), num()
            segs.append(("L", [(x, y)]))
            last_cubic = last_q = None
        elif cmd == "H":
            x = num()
            segs.append(("L", [(x, y)]))
            last_cubic = last_q = None
        elif cmd == "V":
            y = num()
            segs.append(("L", [(x, y)]))
            last_cubic = last_q = None
        elif cmd == "C":
            p1 = (num(), num())
            p2 = (num(), num())
            x, y = num(), num()
            segs.append(("C", [p1, p2, (x, y)]))
            last_cubic, last_q = p2, None
        elif cmd == "S":
            cx0, cy0 = x, y
            p2 = (num(), num())
            x, y = num(), num()
            p1 = (2 * cx0 - last_cubic[0], 2 * cy0 - last_cubic[1]) if last_cubic else (cx0, cy0)
            segs.append(("C", [p1, p2, (x, y)]))
            last_cubic, last_q = p2, None
        elif cmd == "Q":
            c = (num(), num())
            x, y = num(), num()
            segs.append(("Q", [c, (x, y)]))
            last_q, last_cubic = c, None
        elif cmd == "T":
            cx0, cy0 = x, y
            c = (2 * cx0 - last_q[0], 2 * cy0 - last_q[1]) if last_q else (cx0, cy0)
            x, y = num(), num()
            segs.append(("Q", [c, (x, y)]))
            last_q, last_cubic = c, None
        elif cmd == "A":
            rx, ry, rot, large, sweep = num(), num(), num(), num(), num()
            x1, y1 = num(), num()
            segs.extend(_arc_to_beziers(x, y, rx, ry, rot, large, sweep, x1, y1))
            x, y = x1, y1
            last_cubic = last_q = None
        else:
            raise MotifError(f"bad path data: unexpected command {cmd!r}")
    if not segs:
        raise MotifError("bad path data: empty path")
    return segs


def _fmt(v: float) -> str:
    v = round(v, 3)
    if v == 0:
        v = 0.0
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


def segments_to_d(segs: list[Segment]) -> str:
    """Segments back to compact absolute path data."""
    parts: list[str] = []
    for verb, pts in segs:
        if verb == "Z":
            parts.append("Z")
        else:
            parts.append(verb + " ".join(_fmt(v) for p in pts for v in p))
    return " ".join(parts)


def d_to_pathops(d: str) -> pathops.Path:
    """Path data to a skia-pathops Path (empty string gives an empty Path)."""
    path = pathops.Path()
    if not d.strip():
        return path
    for verb, pts in parse_d(d):
        if verb == "M":
            path.moveTo(*pts[0])
        elif verb == "L":
            path.lineTo(*pts[0])
        elif verb == "C":
            path.cubicTo(pts[0][0], pts[0][1], pts[1][0], pts[1][1], pts[2][0], pts[2][1])
        elif verb == "Q":
            path.quadTo(pts[0][0], pts[0][1], pts[1][0], pts[1][1])
        else:
            path.close()
    return path


def pathops_to_d(path: pathops.Path) -> str:
    """A skia-pathops Path back to absolute path data (fills only, never strokes)."""
    with contextlib.suppress(AttributeError):
        path.convertConicsToQuads()
    verbs = list(path.verbs)
    points = list(path.points)
    segs: list[Segment] = []
    k = 0
    for verb in verbs:
        name = verb.name if hasattr(verb, "name") else str(verb)
        if name == "MOVE":
            segs.append(("M", [points[k]]))
            k += 1
        elif name == "LINE":
            segs.append(("L", [points[k]]))
            k += 1
        elif name == "QUAD":
            segs.append(("Q", [points[k], points[k + 1]]))
            k += 2
        elif name == "CUBIC":
            segs.append(("C", [points[k], points[k + 1], points[k + 2]]))
            k += 3
        elif name == "CLOSE":
            segs.append(("Z", []))
        else:
            raise MotifError(f"pathops emitted an unsupported verb {name!r}")
    return segments_to_d(segs)


def _empty(d: str) -> bool:
    return not d.strip()


def _boolean(a: str, b: str, operation: pathops.PathOp) -> str:
    if operation == pathops.PathOp.UNION:
        if _empty(a):
            return b
        if _empty(b):
            return a
    elif operation == pathops.PathOp.DIFFERENCE:
        if _empty(a) or _empty(b):
            return a
    elif operation == pathops.PathOp.INTERSECTION:
        if _empty(a) or _empty(b):
            return ""
    elif operation == pathops.PathOp.XOR:
        if _empty(a):
            return b
        if _empty(b):
            return a
    return pathops_to_d(pathops.op(d_to_pathops(a), d_to_pathops(b), operation))


def union(a: str, b: str) -> str:
    """Boolean union of two path-d strings."""
    return _boolean(a, b, pathops.PathOp.UNION)


def difference(a: str, b: str) -> str:
    """``a`` minus ``b``, as path-d."""
    return _boolean(a, b, pathops.PathOp.DIFFERENCE)


def intersection(a: str, b: str) -> str:
    """Overlap of ``a`` and ``b``, as path-d."""
    return _boolean(a, b, pathops.PathOp.INTERSECTION)


def xor(a: str, b: str) -> str:
    """Either ``a`` or ``b`` but not both, as path-d."""
    return _boolean(a, b, pathops.PathOp.XOR)


def stroke_d(d: str, width: float, cap: str = "round", join: str = "round") -> str:
    """Outline a centerline path (or polyline points) to a filled path-d."""
    caps = {
        "round": pathops.LineCap.ROUND_CAP,
        "butt": pathops.LineCap.BUTT_CAP,
        "square": pathops.LineCap.SQUARE_CAP,
    }
    joins = {
        "round": pathops.LineJoin.ROUND_JOIN,
        "miter": pathops.LineJoin.MITER_JOIN,
        "bevel": pathops.LineJoin.BEVEL_JOIN,
    }
    if cap not in caps:
        raise MotifError(f"bad cap {cap!r}; want one of {sorted(caps)}")
    if join not in joins:
        raise MotifError(f"bad join {join!r}; want one of {sorted(joins)}")
    path = d_to_pathops(d)
    path.stroke(width, caps[cap], joins[join], 4.0)
    return pathops_to_d(path)


def transform_d(
    d: str, scale: float = 1.0, rotate_deg: float = 0.0, translate: tuple[float, float] = (0.0, 0.0)
) -> str:
    """Affine-transform every point (including curve controls) of a path-d."""
    angle = math.radians(rotate_deg)
    cos, sin = math.cos(angle) * scale, math.sin(angle) * scale
    tx, ty = translate

    def move(p: tuple[float, float]) -> tuple[float, float]:
        return (cos * p[0] - sin * p[1] + tx, sin * p[0] + cos * p[1] + ty)

    return segments_to_d([(v, [move(p) for p in pts]) for v, pts in parse_d(d)])


def bbox_of_d(d: str) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) over every point and control point."""
    xs, ys = [], []
    for _, pts in parse_d(d):
        for p in pts:
            xs.append(p[0])
            ys.append(p[1])
    if not xs:
        raise MotifError("cannot box an empty path")
    return (min(xs), min(ys), max(xs), max(ys))


def fit(d: str, box: tuple[float, float, float, float] | None = None) -> str:
    """Scale a path-d to fit a box, preserving aspect ratio, centered.

    The default box is the square inscribed in the radius-470 circle, so even
    the fitted bounding box's corners stay inside the circle.
    """
    if box is None:
        half = RADIUS / math.sqrt(2)
        box = (CX - half, CY - half, 2 * half, 2 * half)
    bx, by, bw, bh = box
    x0, y0, x1, y1 = bbox_of_d(d)
    w, h = x1 - x0, y1 - y0
    s = min(bw / w, bh / h) if w > 0 and h > 0 else 1.0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return transform_d(d, scale=s, translate=(bx + bw / 2 - s * cx, by + bh / 2 - s * cy))


def _bez(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    u = 1 - t
    return (
        u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
    )


def _quad(
    p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], t: float
) -> tuple[float, float]:
    u = 1 - t
    return (
        u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
    )


def flatten_d(d: str, steps: int = FLATTEN_STEPS) -> list[list[tuple[float, float]]]:
    """Path-d to closed polylines: every curve sampled at ``steps`` segments."""
    contours: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    start = (0.0, 0.0)
    for verb, pts in parse_d(d):
        if verb == "M":
            if current:
                if current[0] != current[-1]:
                    current.append(current[0])
                contours.append(current)
            start = pts[0]
            current = [start]
        elif verb == "L":
            current.append(pts[0])
        elif verb in ("C", "Q"):
            p0 = current[-1]
            for k in range(1, steps + 1):
                t = k / steps
                current.append(_bez(p0, *pts, t) if verb == "C" else _quad(p0, *pts, t))
        else:  # Z
            if current and current[0] != current[-1]:
                current.append(current[0])
            if current:
                contours.append(current)
            current = []
    if current:
        if current[0] != current[-1]:
            current.append(current[0])
        contours.append(current)
    return contours


def poly_area(contour: list[tuple[float, float]] | list[list[float]]) -> float:
    """Absolute shoelace area of a closed polyline."""
    pts = [(float(p[0]), float(p[1])) for p in contour]
    if len(pts) < 3:
        return 0.0
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in pairwise(pts)) / 2)


# ----------------------------------------------------------------------------
# Motif builder: the API agent-written motif.py files use
# ----------------------------------------------------------------------------

_KAPPA = 0.5522847498307936


@dataclass
class Motif:
    """Accumulates contract-clean paths; :meth:`save` writes motif.svg + motif.json."""

    _paths: list[dict] = field(default_factory=list)

    # -- shapes (all return plain path-d strings) --
    @staticmethod
    def circle(cx: float, cy: float, r: float) -> str:
        """A circle as four cubic curves."""
        k = _KAPPA * r
        return segments_to_d(
            [
                ("M", [(cx + r, cy)]),
                ("C", [(cx + r, cy + k), (cx + k, cy + r), (cx, cy + r)]),
                ("C", [(cx - k, cy + r), (cx - r, cy + k), (cx - r, cy)]),
                ("C", [(cx - r, cy - k), (cx - k, cy - r), (cx, cy - r)]),
                ("C", [(cx + k, cy - r), (cx + r, cy - k), (cx + r, cy)]),
                ("Z", []),
            ]
        )

    @staticmethod
    def rect(x: float, y: float, w: float, h: float, rx: float = 0.0) -> str:
        """A rectangle, optionally with rounded corners of radius ``rx``."""
        rx = max(0.0, min(rx, w / 2, h / 2))
        if rx == 0:
            return segments_to_d(
                [
                    ("M", [(x, y)]),
                    ("L", [(x + w, y)]),
                    ("L", [(x + w, y + h)]),
                    ("L", [(x, y + h)]),
                    ("Z", []),
                ]
            )
        return segments_to_d(
            [
                ("M", [(x + rx, y)]),
                ("L", [(x + w - rx, y)]),
                ("Q", [(x + w, y), (x + w, y + rx)]),
                ("L", [(x + w, y + h - rx)]),
                ("Q", [(x + w, y + h), (x + w - rx, y + h)]),
                ("L", [(x + rx, y + h)]),
                ("Q", [(x, y + h), (x, y + h - rx)]),
                ("L", [(x, y + rx)]),
                ("Q", [(x, y), (x + rx, y)]),
                ("Z", []),
            ]
        )

    @staticmethod
    def polygon(points: Sequence[Sequence[float]]) -> str:
        """A closed polygon through ``points``."""
        pts = [(float(p[0]), float(p[1])) for p in points]
        if len(pts) < 3:
            raise MotifError(f"a polygon needs 3+ points, got {len(pts)}")
        return segments_to_d([("M", [pts[0]])] + [("L", [p]) for p in pts[1:]] + [("Z", [])])

    @staticmethod
    def regular_polygon(cx: float, cy: float, r: float, n: int, rotation_deg: float = -90.0) -> str:
        """An n-gon of circumradius ``r``."""
        if n < 3:
            raise MotifError(f"a regular polygon needs 3+ sides, got {n}")
        a0 = math.radians(rotation_deg)
        pts = [
            (
                cx + r * math.cos(a0 + 2 * math.pi * k / n),
                cy + r * math.sin(a0 + 2 * math.pi * k / n),
            )
            for k in range(n)
        ]
        return Motif.polygon(pts)

    @staticmethod
    def star(
        cx: float,
        cy: float,
        r_outer: float,
        r_inner: float,
        points: int = 5,
        rotation_deg: float = -90.0,
    ) -> str:
        """A star alternating outer/inner radius."""
        if points < 2:
            raise MotifError(f"a star needs 2+ points, got {points}")
        if r_inner <= 0 or r_outer <= 0:
            raise MotifError("star radii must be positive")
        a0 = math.radians(rotation_deg)
        pts = []
        for k in range(2 * points):
            r = r_outer if k % 2 == 0 else r_inner
            a = a0 + math.pi * k / points
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return Motif.polygon(pts)

    @staticmethod
    def path(d: str) -> str:
        """Raw path-d, parsed now so a broken string fails at authoring time."""
        return segments_to_d(parse_d(d))

    @staticmethod
    def glyphs(
        text: str,
        font_spec: str,
        size: float,
        x: float,
        y: float,
        *,
        anchor: str = "baseline",
        tracking: float = 0.0,
    ) -> tuple[str, float]:
        """Set text as path-d plus its advance in px; ``anchor`` centers the block at (x, y)."""
        if anchor not in ("baseline", "center"):
            raise MotifError(f"bad anchor {anchor!r}; want 'baseline' or 'center'")
        from logo_maker.fonts import advances, metrics, text_path

        if anchor == "center":
            adv = sum(advances(text, font_spec)) * size
            em = metrics(font_spec)
            x -= adv / 2
            y += (em["ascender"] + em["descender"]) / 2 * size
        return text_path(text, font_spec, size, x, y, tracking=tracking)

    @staticmethod
    def stroke(points_or_d, width: float, *, cap: str = "round", join: str = "round") -> str:
        """Outline point lists (``[(x, y), ...]``) or a centerline path-d to a fill."""
        d = points_or_d if isinstance(points_or_d, str) else Motif._polyline(points_or_d)
        return stroke_d(Motif.path(d), width, cap=cap, join=join)

    @staticmethod
    def _polyline(points) -> str:
        pts = [(float(p[0]), float(p[1])) for p in points]
        if len(pts) < 2:
            raise MotifError("a stroke needs 2+ points")
        return segments_to_d([("M", [pts[0]])] + [("L", [p]) for p in pts[1:]])

    # -- booleans and placement (thin wrappers so scripts read fluently) --
    @staticmethod
    def union(a: str, b: str) -> str:
        return union(a, b)

    @staticmethod
    def difference(a: str, b: str) -> str:
        return difference(a, b)

    @staticmethod
    def intersection(a: str, b: str) -> str:
        return intersection(a, b)

    @staticmethod
    def xor(a: str, b: str) -> str:
        return xor(a, b)

    @staticmethod
    def transform(
        d: str,
        scale: float = 1.0,
        rotate_deg: float = 0.0,
        translate: tuple[float, float] = (0.0, 0.0),
    ) -> str:
        return transform_d(d, scale=scale, rotate_deg=rotate_deg, translate=translate)

    @staticmethod
    def fit(d: str, box: tuple[float, float, float, float] | None = None) -> str:
        return fit(d, box)

    # -- accumulation --
    def add(
        self,
        id: str,
        d: str,
        *,
        fill: str,
        role: str = "primary",
        height: float = 1.0,
        layer: int = 0,
    ) -> str:
        """Add one contract-clean path; returns the id."""
        if any(p["id"] == id for p in self._paths):
            raise MotifError(f"duplicate path id {id!r}")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", id):
            raise MotifError(f"bad path id {id!r}")
        if not HEX_RE.match(fill):
            raise MotifError(f"bad fill {fill!r}; want #RRGGBB")
        if role not in ROLES:
            raise MotifError(f"bad role {role!r}; want one of {ROLES}")
        self._paths.append(
            {
                "id": id,
                "d": Motif.path(d),
                "fill": fill.upper(),
                "role": role,
                "height": float(height),
                "layer": int(layer),
            }
        )
        return id

    def save(self, concept_dir: Path) -> Path:
        """Write motif.svg (only paths, absolute coords) then motif.json; returns the svg."""
        concept_dir = Path(concept_dir)
        concept_dir.mkdir(parents=True, exist_ok=True)
        drawing = dw.Drawing(
            int(VIEWBOX), int(VIEWBOX)
        )  # ints: floats print as 1000.0 and fail validate
        for p in self._paths:
            drawing.append(
                dw.Path(
                    d=p["d"],
                    fill=p["fill"],
                    id=p["id"],
                    **{
                        "data-role": p["role"],
                        "data-height": _fmt(p["height"]),
                        "data-layer": str(p["layer"]),
                    },
                )
            )
        text = drawing.as_svg()
        text = re.sub(r"<defs>\s*</defs>\s*", "", text)  # empty defs would fail "only paths"
        svg = concept_dir / "motif.svg"
        svg.write_text(text)
        flatten(svg, concept_dir / "motif.json")
        return svg


# ----------------------------------------------------------------------------
# Validation and derived formats
# ----------------------------------------------------------------------------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def svg_root(svg: Path) -> ET.Element:
    """Parse an SVG file our own toolchain wrote (never fetched XML)."""
    return ET.parse(svg).getroot()  # noqa: S314 - local concept and tool files only


def svg_root_text(text: str) -> ET.Element:
    """Parse SVG markup our own toolchain produced (never fetched XML)."""
    return ET.fromstring(text)  # noqa: S314 - tool-generated markup only


def validate(svg: Path) -> list[str]:
    """Every contract violation in a motif.svg; empty means it is clean."""
    problems: list[str] = []
    try:
        root = svg_root(svg)
    except ET.ParseError as exc:
        return [f"{svg}: not valid XML: {exc}"]
    if _local(root.tag) != "svg":
        return [f"{svg}: root is <{_local(root.tag)}>, want <svg>"]
    if root.get("viewBox", "").split() != ["0", "0", "1000", "1000"]:
        problems.append(f"viewBox is {root.get('viewBox')!r}, want '0 0 1000 1000'")
    seen: set[str] = set()
    for child in root:
        tag = _local(child.tag)
        if tag == "defs" and len(child) == 0 and not (child.text or "").strip():
            continue
        if tag != "path":
            problems.append(f"<{tag}> is not allowed; only <path> elements may appear")
            continue
        pid = child.get("id", "")
        if not pid:
            problems.append("a <path> has no id")
        elif pid in seen:
            problems.append(f"duplicate path id {pid!r}")
        seen.add(pid)
        fill = child.get("fill", "")
        if not HEX_RE.match(fill):
            problems.append(f"path {pid!r}: fill {fill!r} is not #RRGGBB")
        for attr in ("transform", "stroke", "stroke-width"):
            if child.get(attr) is not None:
                problems.append(
                    f"path {pid!r}: {attr} is forbidden "
                    f"({'outlines' if 'stroke' in attr else 'baked coordinates'} only)"
                )
        if child.get("d", "") == "":
            problems.append(f"path {pid!r}: empty d")
            continue
        try:
            segs = parse_d(child.get("d", ""))
        except MotifError as exc:
            problems.append(f"path {pid!r}: {exc}")
            continue
        role = child.get("data-role", "primary")
        if role not in ROLES:
            problems.append(f"path {pid!r}: data-role {role!r} is not one of {ROLES}")
        try:
            float(child.get("data-height", "1"))
        except ValueError:
            problems.append(
                f"path {pid!r}: data-height {child.get('data-height')!r} is not a number"
            )
        try:
            int(child.get("data-layer", "0"))
        except ValueError:
            problems.append(
                f"path {pid!r}: data-layer {child.get('data-layer')!r} is not an integer"
            )
        for _, pts in segs:
            for px, py in pts:
                if math.hypot(px - CX, py - CY) > RADIUS + GEOM_TOL:
                    problems.append(
                        f"path {pid!r}: point ({px:.1f}, {py:.1f}) leaves "
                        f"the radius-{RADIUS:.0f} circle"
                    )
                    break
            else:
                continue
            break
    return problems


def flatten(svg: Path, out: Path | None = None) -> dict:
    """Derive motif.json: per-path overlap removal, curves at 12 steps, closed contours.

    Writes next to the svg when ``out`` is None.
    """
    svg = Path(svg)
    problems = validate(svg)
    if problems:
        raise MotifError(f"{svg} breaks the motif contract: " + "; ".join(problems[:5]))
    root = svg_root(svg)
    layers = []
    for child in root:
        if _local(child.tag) != "path":
            continue
        pid = child.get("id", "")
        path = d_to_pathops(child.get("d", ""))
        clean = pathops.op(path, d_to_pathops(child.get("d", "")), pathops.PathOp.UNION)
        contours = []
        for contour in flatten_d(pathops_to_d(clean)):
            contours.append([[round(x, 3), round(y, 3)] for x, y in contour])
        layers.append(
            {
                "id": pid,
                "fill": child.get("fill", "").upper(),
                "role": child.get("data-role", "primary"),
                "height": float(child.get("data-height", "1")),
                "layer": int(child.get("data-layer", "0")),
                "contours": contours,
            }
        )
    data = {"viewbox": 1000, "layers": layers}
    dest = Path(out) if out is not None else svg.parent / "motif.json"
    dest.write_text(json.dumps(data))
    return data


def rasterize(svg: Path, size: int, out: Path, *, background: str | None = None) -> Path:
    """Render a motif svg to a square PNG of ``size`` px (transparent unless given a bg)."""
    out = Path(out)
    png = resvg_py.svg_to_bytes(
        svg_string=Path(svg).read_text(), width=size, height=size, background=background
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png)
    return out


def mono(svg: Path, ink: str, out: Path) -> Path:
    """Recopy a motif svg with every fill set to one ink (for the mono export)."""
    if not HEX_RE.match(ink):
        raise MotifError(f"bad ink {ink!r}; want #RRGGBB")
    root = svg_root(svg)
    for child in root:
        if _local(child.tag) == "path":
            child.set("fill", ink.upper())
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.ElementTree(root).write(out, encoding="unicode", xml_declaration=True)
    return out


def silhouette(motif_json: dict) -> list[list[list[float]]]:
    """Union every layer's outer shape into one set of closed contours."""
    acc: pathops.Path | None = None
    for layer in motif_json.get("layers", []):
        for contour in layer.get("contours", []):
            path = pathops.Path()
            path.moveTo(contour[0][0], contour[0][1])
            for pt in contour[1:]:
                path.lineTo(pt[0], pt[1])
            path.close()
            acc = path if acc is None else pathops.op(acc, path, pathops.PathOp.UNION)
    if acc is None:
        return []
    return [[[round(x, 3), round(y, 3)] for x, y in c] for c in flatten_d(pathops_to_d(acc))]


def run_motif_script(concept_dir: Path, *, timeout: float = 120) -> Path:
    """Run concept_dir/motif.py (as the agent wrote it), then validate and flatten.

    Raises MotifError carrying the script's stderr; returns the svg path.
    """
    concept_dir = Path(concept_dir)
    script = concept_dir / "motif.py"
    if not script.exists():
        raise MotifError(f"no motif.py in {concept_dir}")
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=concept_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MotifError(f"motif.py timed out after {timeout:.0f}s") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-2000:]
        raise MotifError(f"motif.py exited {proc.returncode}: {tail}")
    svg = concept_dir / "motif.svg"
    if not svg.exists():
        raise MotifError("motif.py ran but wrote no motif.svg (call Motif.save)")
    problems = validate(svg)
    if problems:
        raise MotifError("motif.svg breaks the contract: " + "; ".join(problems[:8]))
    flatten(svg, concept_dir / "motif.json")
    return svg


def size_sheet(svg: Path, out: Path) -> Path:
    """Render 16/32/48/64/180 px previews side by side for agent review."""
    svg = Path(svg)
    sizes = (16, 32, 48, 64, 180)
    thumbs = [
        Image.open(io.BytesIO(resvg_py.svg_to_bytes(svg_string=svg.read_text(), width=s, height=s)))
        for s in sizes
    ]
    pad, label_h = 16, 22
    widths = [t.width for t in thumbs]
    sheet = Image.new(
        "RGBA",
        (sum(widths) + pad * (len(thumbs) + 1), max(t.height for t in thumbs) + pad * 2 + label_h),
        (255, 255, 255, 255),
    )
    draw = ImageDraw.Draw(sheet)
    # Checkerboard so near-white and near-black ink both stay visible at this gate.
    cell = 10
    for yy in range(0, sheet.height, cell):
        for xx in range(0, sheet.width, cell):
            shade = (
                (250, 250, 250, 255) if (xx // cell + yy // cell) % 2 == 0 else (205, 205, 205, 255)
            )
            draw.rectangle([xx, yy, xx + cell - 1, yy + cell - 1], fill=shade)
    x = pad
    for size, thumb in zip(sizes, thumbs, strict=True):
        y = pad + (max(t.height for t in thumbs) - thumb.height)
        sheet.alpha_composite(thumb, (x, y))
        draw.text((x, y + thumb.height + 4), f"{size}px", fill=(60, 60, 60, 255))
        x += thumb.width + pad
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(out)
    return out
