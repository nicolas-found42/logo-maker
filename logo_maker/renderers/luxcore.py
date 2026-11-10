"""LuxCoreRender alternate renderer: scene export -> lit RGBA PNG.

Maps the export materials to LuxCore `disney` materials, area/point lights
to emissive meshes, and sun lights to native `sun` sources. Renders with
PATHCPU (or PATHOCL when OpenCL devices exist) and a tonemapped
RGBA film output, which stays transparent where nothing is hit.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import trimesh

from logo_maker.renderers import load_export, resolve, scaled_size, spp_for

_ENGINE_CPU = "PATHCPU"
_ENGINE_OCL = "PATHOCL"


def _engine() -> str:
    """PATHCPU unless LOGO_MAKER_LUXCORE_ENGINE=PATHOCL with OpenCL devices present."""
    import os

    import pyluxcore

    if os.environ.get("LOGO_MAKER_LUXCORE_ENGINE", "").upper() != "PATHOCL":
        return _ENGINE_CPU
    try:
        devices = pyluxcore.GetOpenCLDeviceList()
    except Exception:
        return _ENGINE_CPU
    return _ENGINE_OCL if devices else _ENGINE_CPU


def _vec(values) -> list[float]:
    return [float(v) for v in np.asarray(values, dtype=float).ravel()]


def _set(props, key: str, value) -> None:
    """Set one SDL property; pyluxcore wants a value list, not a bare scalar."""
    import pyluxcore

    vals = list(value) if isinstance(value, (list, tuple)) else [value]
    props.Set(pyluxcore.Property(key, vals))


def _disney(props, name: str, mat: dict) -> None:
    """Export material dict -> LuxCore `disney` (documented approximations)."""
    base = f"scene.materials.{name}"
    # Export colors are linear RGBA; LuxCore constant textures take RGB.
    color = _vec(mat.get("base_color_linear", (0.8, 0.8, 0.8)))[:3]
    _set(props, f"{base}.type", "disney")
    _set(props, f"{base}.basecolor", color)
    _set(props, f"{base}.metallic", float(mat.get("metallic", 0.0)))
    _set(props, f"{base}.roughness", float(np.clip(mat.get("roughness", 0.5), 0.03, 1.0)))
    _set(props, f"{base}.clearcoat", float(mat.get("coat", 0.0)))
    _set(
        props,
        f"{base}.clearcoatgloss",
        float(np.clip(1.0 - mat.get("coat_roughness", 0.2), 0.02, 1.0)),
    )


def _frame(loc: np.ndarray, tgt: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Right/up basis for a quad at `loc` facing `tgt` (mirrors mitsuba's rect)."""
    fwd = tgt - loc
    fwd /= np.linalg.norm(fwd)
    hint = np.array([0.0, 0.0, 1.0]) if abs(fwd[2]) < 0.99 else np.array([0.0, 1.0, 0.0])
    right = np.cross(fwd, hint)
    right /= np.linalg.norm(right)
    return right, np.cross(right, fwd)


def _emissive_quad(path: Path, loc: np.ndarray, tgt: np.ndarray, size: float) -> None:
    """Single quad in world coords facing the target (identity transform)."""
    right, up = _frame(loc, tgt)
    half = size / 2
    corners = np.array(
        [
            loc - right * half - up * half,
            loc + right * half - up * half,
            loc + right * half + up * half,
            loc - right * half + up * half,
        ]
    )
    mesh = trimesh.Trimesh(vertices=corners, faces=[[0, 1, 2], [0, 2, 3]], process=True)
    fwd = (tgt - loc) / np.linalg.norm(tgt - loc)
    mesh.vertex_normals = np.tile(fwd, (4, 1))
    mesh.export(path)


def _emissive_ball(path: Path, loc: np.ndarray, diameter: float) -> None:
    mesh = trimesh.creation.icosphere(radius=max(diameter / 2, 1e-3), subdivisions=2)
    mesh.apply_translation(loc)
    mesh.export(path)


def render(export_json: Path, out_png: Path, *, quality: str, resolution: int) -> Path:
    """Render the scene export with LuxCore to an RGBA PNG."""
    import pyluxcore

    pyluxcore.Init()
    data, concept_dir = load_export(export_json)
    width, height = scaled_size(data, resolution)
    spp = spp_for(quality)
    camera = data.get("camera", {})
    session_dir = concept_dir / "meshes" / ".luxcore"
    session_dir.mkdir(parents=True, exist_ok=True)

    props = pyluxcore.Properties()
    _set(props, "scene.camera.lookat.orig", _vec(camera.get("location", (0, -3, 2))))
    _set(props, "scene.camera.lookat.target", _vec(camera.get("target", (0, 0, 0))))
    _set(props, "scene.camera.up", _vec(camera.get("up", (0, 0, 1))))
    _set(props, "scene.camera.fieldofview", float(camera.get("fov_deg", 35.0)))

    for name, mat in data.get("materials", {}).items():
        _disney(props, name, mat)
    for i, obj in enumerate(data.get("objects", [])):
        mesh_path = resolve(concept_dir, obj["mesh"])
        if not mesh_path.is_file():
            raise FileNotFoundError(f"mesh not found: {mesh_path}")
        _set(props, f"scene.objects.mesh_{i}.ply", str(mesh_path))
        _set(props, f"scene.objects.mesh_{i}.material", obj.get("material", "surface"))

    for i, light in enumerate(data.get("lights", [])):
        kind = light.get("type", "point")
        color = np.asarray(light.get("color_linear", (1.0, 1.0, 1.0)), dtype=float)[:3]
        power = float(light.get("power_w", 10.0))
        loc = np.asarray(light.get("location", (0, 0, 5)), dtype=float)
        tgt = np.asarray(light.get("target", (0, 0, 0)), dtype=float)
        if kind == "sun":
            # LuxCore sun dir points from the scene toward the sun.
            direction = loc - tgt
            direction /= np.linalg.norm(direction)
            _set(props, f"scene.lights.sun_{i}.type", "sun")
            _set(props, f"scene.lights.sun_{i}.dir", _vec(direction))
            _set(props, f"scene.lights.sun_{i}.gain", _vec(color * power))
            _set(props, f"scene.lights.sun_{i}.turbidity", 2.2)
        else:
            if kind == "area":
                size = max(float(light.get("size", 1.0)), 1e-3)
                glow_path = session_dir / f"light_{i}.ply"
                _emissive_quad(glow_path, loc, tgt, size)
                # Emitted radiance (W/m^2/sr): power spread over the rect.
                radiance = color * power / (size * size)
            else:  # point
                size = max(float(light.get("size", 0.2)), 1e-3)
                glow_path = session_dir / f"light_{i}.ply"
                _emissive_ball(glow_path, loc, size)
                radiance = color * power / (4 * np.pi * (size / 2) ** 2)
            mat_name = f"lightmat_{i}"
            _set(props, f"scene.materials.{mat_name}.type", "matte")
            _set(props, f"scene.materials.{mat_name}.emission", _vec(radiance))
            _set(props, f"scene.objects.light_{i}.ply", str(glow_path))
            _set(props, f"scene.objects.light_{i}.material", mat_name)

    scene = pyluxcore.Scene()
    scene.Parse(props)

    config_props = pyluxcore.Properties()
    _set(config_props, "renderengine.type", _engine())
    _set(config_props, "sampler.type", "SOBOL")
    _set(config_props, "film.width", width)
    _set(config_props, "film.height", height)
    _set(config_props, "film.outputs.0.type", "RGBA_IMAGEPIPELINE")
    _set(config_props, "film.outputs.0.index", 0)
    _set(config_props, "film.outputs.0.filename", str(out_png.absolute()))
    _set(config_props, "film.imagepipelines.0.0.type", "TONEMAP_LINEAR")
    _set(config_props, "film.imagepipelines.0.1.type", "GAMMA_CORRECTION")
    _set(config_props, "film.imagepipelines.0.1.value", 2.2)
    _set(config_props, "batch.haltspp", spp)
    _set(config_props, "batch.halttime", 1200)
    config = pyluxcore.RenderConfig(config_props, scene)
    session = pyluxcore.RenderSession(config)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    session.Start()
    try:
        # LuxCore checks batch.haltspp/halttime only inside UpdateStats() (Film::RunTests);
        # WaitForDone() just joins the render threads, which never stop on their own.
        while not session.HasDone():
            time.sleep(0.05)
            session.UpdateStats()
    finally:
        session.Stop()
    session.GetFilm().SaveOutputs()
    if not out_png.is_file():
        raise RuntimeError(f"luxcore finished without writing {out_png}")
    return out_png
