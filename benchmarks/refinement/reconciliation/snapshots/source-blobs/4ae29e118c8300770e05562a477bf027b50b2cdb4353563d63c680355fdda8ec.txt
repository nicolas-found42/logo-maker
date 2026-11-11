"""Every 2D/motif tool logo-maker can use: fonts, vector helpers, renderers, tracers."""

from __future__ import annotations

from logo_maker.adapters import Adapter, binary, node_package, python_module

GO = "go install github.com/fogleman/primitive@latest and add $(go env GOPATH)/bin to PATH"


def _rough() -> str | None:
    for package in ("roughjs", "svg2roughjs"):
        if (missing := node_package(package)()) is not None:
            return missing
    return None


def _primitive() -> str | None:
    import os
    import shutil
    import subprocess

    candidates = [shutil.which("primitive")]
    try:
        gopath = subprocess.run(
            ["go", "env", "GOPATH"], capture_output=True, text=True, timeout=15
        ).stdout.strip()
        candidates.append(os.path.join(gopath, "bin", "primitive"))
    except (OSError, subprocess.TimeoutExpired):
        pass
    candidates.append(os.path.join(os.path.expanduser("~"), "go", "bin", "primitive"))
    for hit in candidates:
        if hit and os.path.isfile(hit) and os.access(hit, os.X_OK):
            return None
    return "primitive not on PATH (nor in GOPATH/bin)"


ADAPTERS: list[Adapter] = [
    Adapter(
        "fontTools",
        "motif_2d",
        "MIT",
        "Google Fonts download, variable-axis instancing, and text outlines",
        "logo_maker.fonts:resolve",
        python_module("fontTools"),
        "just setup",
    ),
    Adapter(
        "skia-pathops",
        "motif_2d",
        "BSD-3-Clause",
        "booleans, stroking, and overlap removal behind motif geometry",
        "logo_maker.motif:union",
        python_module("pathops"),
        "just setup",
    ),
    Adapter(
        "drawsvg",
        "motif_2d",
        "MIT",
        "writes the contract-clean motif.svg document",
        "logo_maker.motif:Motif.save",
        python_module("drawsvg"),
        "just setup",
    ),
    Adapter(
        "resvg-py",
        "motif_2d",
        "MPL-2.0",
        "rasters motif.svg to PNG previews at any size",
        "logo_maker.motif:rasterize",
        python_module("resvg_py"),
        "just setup",
    ),
    Adapter(
        "Pillow",
        "motif_2d",
        "MIT-CMU",
        "composes size sheets and prepares reference images",
        "logo_maker.motif:size_sheet",
        python_module("PIL"),
        "just setup",
    ),
    Adapter(
        "vtracer",
        "motif_2d",
        "MIT",
        "traces use='geometry' references to SVG paths",
        "logo_maker.trace:trace",
        python_module("vtracer"),
        "just setup",
    ),
    Adapter(
        "vpype",
        "motif_2d",
        "MIT",
        "merges and simplifies line art before it is outlined to fills",
        "logo_maker.twod_tools:plotter_lines",
        python_module("vpype"),
        "just setup",
    ),
    Adapter(
        "FontForge",
        "motif_2d",
        "GPL-3.0-or-later",
        "builds ligature glyphs from component glyphs and exports outlines",
        "logo_maker.twod_tools:fontforge_glyphs",
        binary("fontforge"),
        "brew install fontforge",
    ),
    Adapter(
        "primitive",
        "motif_2d",
        "MIT",
        "geometric image abstraction into shapes",
        "logo_maker.twod_tools:primitive_abstract",
        _primitive,
        GO,
    ),
    Adapter(
        "rough.js+svg2roughjs",
        "motif_2d",
        "MIT",
        "hand-drawn wobble of motif paths (generator ops; strokes outlined to fills)",
        "logo_maker.twod_tools:sketchy",
        _rough,
        "just setup",
    ),
    Adapter(
        "perfect-freehand",
        "motif_2d",
        "MIT",
        "pressure-sensitive stroke outlines",
        "logo_maker.twod_tools:freehand",
        node_package("perfect-freehand"),
        "just setup",
    ),
    Adapter(
        "d3-delaunay",
        "motif_2d",
        "ISC",
        "Voronoi cells and Delaunay triangles",
        "logo_maker.twod_tools:voronoi",
        node_package("d3-delaunay"),
        "just setup",
    ),
    Adapter(
        "trianglify",
        "motif_2d",
        "GPL-3.0",
        "low-poly triangle fields from pattern point/poly data (no DOM)",
        "logo_maker.twod_tools:low_poly",
        node_package("trianglify"),
        "just setup",
    ),
    Adapter(
        "heerich",
        "motif_2d",
        "MIT",
        "voxel scenes rendered to SVG polygons",
        "logo_maker.twod_tools:voxels",
        node_package("heerich"),
        "just setup",
    ),
    Adapter(
        "Google Fonts",
        "motif_2d",
        "OFL-1.1 AND Apache-2.0 AND UFL",
        "variable font files (OFL-1.1, Apache-2.0, or UFL per family) with cached licenses",
        "logo_maker.fonts:resolve",
        python_module("httpx"),
        "just setup",
    ),
]
