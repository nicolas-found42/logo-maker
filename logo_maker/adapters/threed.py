"""External tools the 3D slice runs: renderer, geometry libraries, asset sources."""

from __future__ import annotations

from logo_maker.adapters import Adapter, python_module


def _cycles_gpu() -> str | None:
    try:
        import bpy  # noqa: F401
    except ImportError:
        return "python module bpy not installed"
    return None


def _httpx() -> str | None:
    """HDRI downloads use httpx; reachability is not probed (a scene falls back to none)."""
    try:
        import httpx  # noqa: F401
    except ImportError:
        return "python module httpx not installed"
    return None


ADAPTERS: list[Adapter] = [
    Adapter(
        "bpy/Cycles (Metal)",
        "rendering",
        "GPL-3.0-or-later (Blender) / Apache-2.0 (Metal backend use)",
        "Renders every scene on the Apple Silicon GPU",
        "logo_maker.render:_run_builder",
        _cycles_gpu,
        "uv sync (installs bpy==5.2.3)",
    ),
    Adapter(
        "OIDN",
        "rendering",
        "Apache-2.0",
        "GPU denoiser for Cycles previews and finals",
        "logo_maker.blender.settings:apply_quality",
        python_module("bpy"),
        "uv sync (ships with bpy)",
    ),
    Adapter(
        "Blender cloth",
        "geometry_3d",
        "GPL-3.0-or-later",
        "Physics drape for ribbon components (analytic wave fallback)",
        "logo_maker.blender.components:_drape_ribbon",
        python_module("bpy"),
        "uv sync (ships with bpy)",
    ),
    Adapter(
        "Line Art",
        "rendering",
        "GPL-3.0-or-later",
        "Outline strokes for toon and lineart looks (Freestyle fallback)",
        "logo_maker.blender.components:setup_outlines",
        python_module("bpy"),
        "uv sync (ships with bpy)",
    ),
    Adapter(
        "compositor glare/DOF",
        "rendering",
        "GPL-3.0-or-later",
        "Bloom glare mix and camera depth of field when the scene asks",
        "logo_maker.blender.components:setup_compositor",
        python_module("bpy"),
        "uv sync (ships with bpy)",
    ),
    Adapter(
        "manifold3d",
        "geometry_3d",
        "Apache-2.0",
        "Watertight extrusion triangulation and mesh booleans",
        "logo_maker.geometry:boolean_mesh",
        python_module("manifold3d"),
        "uv sync",
    ),
    Adapter(
        "trimesh",
        "geometry_3d",
        "MIT",
        "Mesh assembly, transforms, and PLY export",
        "logo_maker.geometry:save_ply",
        python_module("trimesh"),
        "uv sync",
    ),
    Adapter(
        "Shapely",
        "geometry_3d",
        "BSD-3-Clause",
        "Validates radial profiles for turned solid components",
        "logo_maker.geometry:lathe_mesh",
        python_module("shapely"),
        "uv sync",
    ),
    Adapter(
        "PyMeshLab",
        "geometry_3d",
        "GPL-3.0-or-later",
        "Isotropic remeshing for inflated (SDF) meshes",
        "logo_maker.geometry:inflate_mesh",
        python_module("pymeshlab"),
        "uv sync",
    ),
    Adapter(
        "build123d",
        "geometry_3d",
        "Apache-2.0",
        "Parametric CAD solids for cad components",
        "logo_maker.geometry:cad_mesh",
        python_module("build123d"),
        "uv sync",
    ),
    Adapter(
        "fogleman/sdf",
        "geometry_3d",
        "MIT",
        "Signed-distance-field sampling for soft inflated forms",
        "logo_maker.geometry:inflate_mesh",
        python_module("sdf"),
        "uv sync",
    ),
    Adapter(
        "Poly Haven",
        "materials_lighting",
        "CC0-1.0",
        "HDRI environment maps via api.polyhaven.com",
        "logo_maker.hdri:_polyhaven",
        _httpx,
        'uv sync (httpx); downloads need network, scenes fall back to hdri = "none"',
    ),
    Adapter(
        "ambientCG",
        "materials_lighting",
        "CC0-1.0",
        "HDRI environment maps via the ambientCG API v3",
        "logo_maker.hdri:_ambientcg",
        _httpx,
        'uv sync (httpx); downloads need network, scenes fall back to hdri = "none"',
    ),
]
