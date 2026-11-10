"""Alternate renderers (mitsuba, luxcore, three.js) from a scene export.

The Blender builder writes `concepts/<slug>/meshes/scene_export.json` (see
docs/architecture.md), and one of these renderers renders from it instead of
Cycles. Every renderer has the same signature:

    render(export_json: Path, out_png: Path, *, quality: str, resolution: int) -> Path

`quality` picks sample counts (`test` 64 spp, `preview` 256, `final` 1024+);
`resolution` is the long edge in pixels. Output is an RGBA PNG, transparent
where `world.transparent` is true.
"""

from __future__ import annotations

import json
from pathlib import Path

QUALITY_SPP = {"test": 64, "preview": 256, "final": 1024}

RENDERERS = ("mitsuba", "luxcore", "three")


def load_export(export_json: Path) -> tuple[dict, Path]:
    """Read the export plus the concept dir its relative paths resolve against."""
    data = json.loads(export_json.read_text())
    concept_dir = export_json.parent.parent
    return data, concept_dir


def resolve(concept_dir: Path, rel: str) -> Path:
    """Resolve an export-relative path (or absolute path, e.g. an HDRI) to a file."""
    path = Path(rel)
    if path.is_absolute():
        return path
    return concept_dir / rel


def scaled_size(data: dict, resolution: int) -> tuple[int, int]:
    """Export resolution scaled so the long edge is `resolution` px."""
    width, height = (int(v) for v in data.get("resolution", (resolution, resolution)))
    scale = resolution / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def spp_for(quality: str) -> int:
    try:
        return QUALITY_SPP[quality]
    except KeyError:
        raise ValueError(
            f"unknown quality {quality!r}; expected one of {sorted(QUALITY_SPP)}"
        ) from None


def render(
    renderer: str, export_json: Path, out_png: Path, *, quality: str, resolution: int
) -> Path:
    """Dispatch to the named alternate renderer (see RENDERERS)."""
    if renderer == "mitsuba":
        from logo_maker.renderers.mitsuba import render as run
    elif renderer == "luxcore":
        from logo_maker.renderers.luxcore import render as run
    elif renderer == "three":
        from logo_maker.renderers.three import render as run
    else:
        raise ValueError(f"unknown renderer {renderer!r}; expected one of {RENDERERS}")
    return run(export_json, out_png, quality=quality, resolution=resolution)
