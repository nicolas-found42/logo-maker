"""Mitsuba 3 alternate renderer: scene export -> lit RGBA PNG.

Maps the export's principled-style materials to Mitsuba's `principled`
BSDF, area lights to emissive rectangles, and the HDRI to an `envmap`
emitter. Uses `metal_ad_rgb` on this Mac when present, else `llvm_ad_rgb`,
else `scalar_rgb`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from logo_maker.renderers import load_export, resolve, scaled_size, spp_for

_VARIANTS = ("metal_ad_rgb", "llvm_ad_rgb", "scalar_rgb")


def _variant() -> str:
    import mitsuba as mi

    for variant in _VARIANTS:
        if variant in mi.variants():
            return variant
    raise RuntimeError(f"no usable mitsuba variant; have {mi.variants()}")


def _rgb(value) -> dict:
    return {"type": "rgb", "value": [float(v) for v in value]}


def _look_at_frame(eye, target, up) -> np.ndarray:
    """Right-handed frame with -Z facing the target (basis for emitter orientation)."""
    eye, target, up = (np.asarray(v, dtype=float) for v in (eye, target, up))
    forward = target - eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, up)
    right /= np.linalg.norm(right)
    true_up = np.cross(right, forward)
    frame = np.eye(4)
    frame[:3, 0], frame[:3, 1], frame[:3, 2], frame[:3, 3] = right, true_up, -forward, eye
    return frame


def _face_frame(eye, target, up) -> np.ndarray:
    """Object-style frame: +Z faces the target (for emissive rectangles)."""
    frame = _look_at_frame(eye, target, up)
    flip = np.diag([-1.0, 1.0, -1.0, 1.0])  # +Z toward target, keep right-handed
    return frame @ flip


def _to_world(frame: np.ndarray):
    """Wrap a 4x4 frame as a Mitsuba transform (dict scenes need the object, not a list)."""
    import mitsuba as mi

    return mi.ScalarTransform4f(frame)


def _bsdf(mat: dict) -> dict:
    """Export material dict -> Mitsuba `principled` BSDF (documented approximations)."""
    sheen = min(float(mat.get("subsurface", 0.0)) + float(mat.get("sheen", 0.0)), 1.0)
    return {
        "type": "principled",
        "base_color": _rgb(mat.get("base_color_linear", (0.8, 0.8, 0.8))),
        "metallic": float(mat.get("metallic", 0.0)),
        "roughness": float(np.clip(mat.get("roughness", 0.5), 0.02, 1.0)),
        "anisotropic": float(mat.get("anisotropy", 0.0)),
        "clearcoat": float(mat.get("coat", 0.0)),
        "clearcoat_gloss": float(np.clip(1.0 - mat.get("coat_roughness", 0.2), 0.02, 1.0)),
        # Subsurface has no principled equivalent here; it softens the lobe as sheen.
        "sheen": sheen,
        "sheen_tint": 0.5,
        "spec_trans": float(mat.get("transmission", 0.0)),
        "eta": float(mat.get("ior", 1.5)),
    }


def _lights(data: dict, scene: dict) -> None:
    for i, light in enumerate(data.get("lights", [])):
        kind = light.get("type", "point")
        color = np.asarray(light.get("color_linear", (1.0, 1.0, 1.0)), dtype=float)
        power = float(light.get("power_w", 10.0))
        loc = np.asarray(light.get("location", (0, 0, 5)), dtype=float)
        tgt = np.asarray(light.get("target", (0, 0, 0)), dtype=float)
        if kind == "area":
            size = float(light.get("size", 1.0))
            frame = _face_frame(loc, tgt, light.get("up", (0, 0, 1)))
            frame[:3, :2] *= size / 2
            frame[:3, 3] = loc
            # Area radiance (W/m^2/sr): power spread over the rect, both faces.
            radiance = (color * power / max(size * size, 1e-6)).tolist()
            scene[f"area_{i}"] = {
                "type": "rectangle",
                "to_world": _to_world(frame),
                "emitter": {"type": "area", "radiance": _rgb(radiance)},
            }
        elif kind == "sun":
            direction = tgt - loc
            direction /= np.linalg.norm(direction)
            scene[f"sun_{i}"] = {
                "type": "directional",
                "direction": [float(v) for v in direction],
                "irradiance": _rgb((color * power).tolist()),
            }
        else:  # point
            scene[f"point_{i}"] = {
                "type": "point",
                "position": [float(v) for v in loc],
                "intensity": _rgb((color * power).tolist()),
            }


def render(export_json: Path, out_png: Path, *, quality: str, resolution: int) -> Path:
    """Render the scene export with Mitsuba 3 to an RGBA PNG."""
    import mitsuba as mi

    mi.set_variant(_variant())
    data, concept_dir = load_export(export_json)
    width, height = scaled_size(data, resolution)
    spp = spp_for(quality)
    world = data.get("world", {})
    camera = data.get("camera", {})

    scene: dict = {
        "type": "scene",
        "integrator": {"type": "path", "max_depth": 8},
        "sensor": {
            "type": "perspective",
            "fov": float(camera.get("fov_deg", 35.0)),
            "to_world": mi.ScalarTransform4f.look_at(
                origin=camera.get("location", (0, -3, 2)),
                target=camera.get("target", (0, 0, 0)),
                up=camera.get("up", (0, 0, 1)),
            ),
            "film": {
                "type": "hdrfilm",
                "width": width,
                "height": height,
                "pixel_format": "rgba",
                "component_format": "float32",
                "rfilter": {"type": "box"},
            },
            "sampler": {"type": "independent", "sample_count": spp},
        },
    }

    # A background emitter (envmap or constant) makes the film alpha opaque, so
    # transparent renders omit it: direct lights still illuminate the object.
    transparent = bool(world.get("transparent", True))
    hdri = world.get("hdri")
    if not transparent:
        if hdri:
            path = resolve(concept_dir, hdri)
            if not path.is_file():
                raise FileNotFoundError(f"HDRI not found: {path}")
            scene["env"] = {
                "type": "envmap",
                "filename": str(path),
                "scale": float(world.get("strength", 1.0)),
            }
        else:
            color = np.asarray(world.get("color_linear", (0.0, 0.0, 0.0)), dtype=float)
            scene["env"] = {
                "type": "constant",
                "radiance": _rgb((color * float(world.get("strength", 1.0))).tolist()),
            }

    _lights(data, scene)

    materials = data.get("materials", {})
    for i, obj in enumerate(data.get("objects", [])):
        mesh_path = resolve(concept_dir, obj["mesh"])
        if not mesh_path.is_file():
            raise FileNotFoundError(f"mesh not found: {mesh_path}")
        mat = materials.get(obj.get("material", ""), {})
        entry: dict = {
            "type": "ply",
            "filename": str(mesh_path),
            "bsdf": _bsdf(mat),
        }
        glow = np.asarray(mat.get("emission_linear", (0, 0, 0)), dtype=float)
        strength = float(mat.get("emission_strength", 0.0))
        if strength > 0 and glow.any():
            entry["emitter"] = {"type": "area", "radiance": _rgb((glow * strength).tolist())}
        scene[f"mesh_{i}"] = entry

    img = mi.render(mi.load_dict(scene), spp=spp)
    rgba = mi.Bitmap(img).convert(mi.Bitmap.PixelFormat.RGBA, mi.Struct.Type.UInt8, True)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    rgba.write(str(out_png))
    return out_png
