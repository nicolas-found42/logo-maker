"""scene.toml: how a motif becomes a 3D object.

`load_scene` reads and validates the agent-authored recipe with errors that name
the field. `from_treatment` emits a starting recipe from a catalog preset.
`compile` resolves everything host-side (fonts, HDRI, meshes) into
`concept_dir/.build/scene.json` for the bpy builder.
"""

from __future__ import annotations

import json
import math
import re
import tomllib
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from logo_maker import geometry
from logo_maker.catalog import lighting as lighting_catalog
from logo_maker.catalog import materials as materials_catalog
from logo_maker.catalog import treatments as treatments_catalog

if TYPE_CHECKING:
    import trimesh

BUILD_DIRNAME = ".build"
_HEX = re.compile(r"#[0-9A-Fa-f]{6}")

QUALITY = {
    "test": {"resolution": 256, "samples": 64, "adaptive": False, "adaptive_threshold": 0.01},
    "preview": {"resolution": 1000, "samples": 256, "adaptive": False, "adaptive_threshold": 0.01},
    "final": {"resolution": 4000, "samples": 4096, "adaptive": True, "adaptive_threshold": 0.01},
}

COMPONENT_KINDS = (
    "plate",
    "recess",
    "rim",
    "relief",
    "extrude",
    "inflate",
    "layers",
    "ring_text",
    "ribbon",
    "tube",
    "voxels",
    "cad",
    "lathe",
    "mesh",
    "bpy",
)

_MATERIAL_PARAMS = (
    "metallic",
    "roughness",
    "coat",
    "coat_roughness",
    "subsurface",
    "sheen",
    "transmission",
    "ior",
    "emission_strength",
    "anisotropy",
    "texture",
    "bump",
    "bump_scale",
)


class SceneError(ValueError):
    """scene.toml names something the builder cannot honor. The message names the field."""


def _field(
    where: str,
    data: dict,
    name: str,
    types: type | tuple | None,
    default: Any = None,
    required: bool = False,
) -> Any:
    if name not in data:
        if required:
            raise SceneError(f"scene.toml: [{where}] missing required field {name!r}")
        return default
    value = data[name]
    allowed = types if isinstance(types, tuple) else (types,)
    if types is not None and (
        not isinstance(value, types) or (isinstance(value, bool) and bool not in allowed)
    ):
        want = " or ".join(t.__name__ for t in allowed if t is not None)
        raise SceneError(f"scene.toml: [{where}] {name}={value!r} must be {want}")
    return value


def _num(
    where: str,
    data: dict,
    name: str,
    default: Any = None,
    required: bool = False,
    lo: float | None = None,
    hi: float | None = None,
    hi_open: bool = False,
) -> float | None:
    value = _field(where, data, name, (int, float), default, required)
    if value is None:
        return None
    value = float(value)
    bad = (lo is not None and value < lo) or (
        hi is not None and (value >= hi if hi_open else value > hi)
    )
    if bad or not math.isfinite(value):
        raise SceneError(f"scene.toml: [{where}] {name}={value} out of range")
    return value


def load_scene(path: Path) -> dict:
    """Read and validate a scene.toml; returns plain data with defaults filled."""
    try:
        raw = tomllib.loads(Path(path).read_text())
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise SceneError(f"scene.toml: cannot parse {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SceneError("scene.toml: top level must hold tables")

    meta = raw.get("meta", {})
    if not isinstance(meta, dict):
        raise SceneError("scene.toml: [meta] must be a table")
    scene: dict[str, Any] = {
        "meta": {
            "concept": _field("meta", meta, "concept", str, required=True),
            "treatment": _field("meta", meta, "treatment", str, required=True),
            "seed": _field("meta", meta, "seed", int, required=True),
        },
    }
    if scene["meta"]["treatment"] not in treatments_catalog():
        raise SceneError(
            f"scene.toml: [meta] treatment={scene['meta']['treatment']!r} "
            f"is not in catalog/treatments.toml"
        )

    camera = raw.get("camera", {})
    if not isinstance(camera, dict):
        raise SceneError("scene.toml: [camera] must be a table")
    scene["camera"] = {
        "tilt_deg": _num("camera", camera, "tilt_deg", 28.0, lo=0.0, hi=89.0),
        "azimuth_deg": _num("camera", camera, "azimuth_deg", 0.0, lo=-180.0, hi=180.0),
        "lens_mm": _num("camera", camera, "lens_mm", 100.0, lo=10.0, hi=400.0),
        "framing": _num("camera", camera, "framing", 0.84, lo=0.05, hi=1.0),
        "sensor_mm": _num("camera", camera, "sensor_mm", 36.0, lo=10.0, hi=80.0),
    }

    mark = raw.get("mark", {})
    if not isinstance(mark, dict):
        raise SceneError("scene.toml: [mark] must be a table")
    scene["mark"] = {"scale": _num("mark", mark, "scale", 1.0, lo=0.1, hi=2.0)}

    light = raw.get("lighting", {})
    if not isinstance(light, dict):
        raise SceneError("scene.toml: [lighting] must be a table")
    rig = _field("lighting", light, "rig", str, "studio_soft")
    if rig not in lighting_catalog():
        raise SceneError(f"scene.toml: [lighting] rig={rig!r} is not in catalog/lighting.toml")
    scene["lighting"] = {
        "rig": rig,
        "hdri": _field("lighting", light, "hdri", str, "none"),
        "hdri_strength": _num("lighting", light, "hdri_strength", 0.45, lo=0.0, hi=4.0),
    }

    render = raw.get("render", {})
    if not isinstance(render, dict):
        raise SceneError("scene.toml: [render] must be a table")
    renderer = _field("render", render, "renderer", str, "cycles")
    if renderer not in ("cycles", "mitsuba", "luxcore", "three"):
        raise SceneError(
            f"scene.toml: [render] renderer={renderer!r} must be cycles|mitsuba|luxcore|three"
        )
    look = _field("render", render, "look", str, "photoreal")
    if look not in ("photoreal", "toon", "lineart"):
        raise SceneError(f"scene.toml: [render] look={look!r} must be photoreal|toon|lineart")
    exposure = _num("render", render, "exposure", 0.0, lo=-32.0, hi=32.0)
    if isinstance(render.get("exposure"), bool):
        raise SceneError("scene.toml: [render] exposure must be a finite number")
    if renderer != "cycles" and exposure != 0.0:
        raise SceneError("scene.toml: [render] nonzero exposure is supported only for cycles")
    scene["render"] = {
        "renderer": renderer,
        "look": look,
        "exposure": exposure,
        "glare": _num("render", render, "glare", 0.0, lo=0.0, hi=1.0),
        "dof_fstop": _num("render", render, "dof_fstop", 0.0, lo=0.0, hi=22.0),
        "adaptive_threshold": _num("render", render, "adaptive_threshold", None, lo=0.0, hi=1.0),
        "max_samples": _num("render", render, "max_samples", None, lo=1.0, hi=1048576),
        "min_samples": _num("render", render, "min_samples", None, lo=0.0, hi=1048576),
        "seed": _num("render", render, "seed", None, lo=0.0, hi=2147483647),
        "adaptive": _field("render", render, "adaptive", bool, None),
        "alpha_cleanup": _field("render", render, "alpha_cleanup", bool, False),
    }

    for name in ("max_samples", "min_samples", "seed"):
        value = scene["render"][name]
        if value is not None and (type(render[name]) is not int):
            raise SceneError(f"scene.toml: [render] {name} must be an integer")
    sampling = raw.get("sampling", {})
    if not isinstance(sampling, dict):
        raise SceneError("scene.toml: [sampling] must be a table")
    scene["sampling"] = {
        "profile": _field("sampling", sampling, "profile", str, None),
        "diagnosis": _field("sampling", sampling, "diagnosis", str, None),
        "wall_seconds": _num("sampling", sampling, "wall_seconds", 1800, lo=0.001),
        "attempt_limit": _field("sampling", sampling, "attempt_limit", int, 2),
        "diagnostic_bytes": _field("sampling", sampling, "diagnostic_bytes", int, 2147483648),
    }
    if not 1 <= scene["sampling"]["attempt_limit"] <= 4:
        raise SceneError("scene.toml: [sampling] attempt_limit must be 1..4")
    if not 0 <= scene["sampling"]["diagnostic_bytes"] <= 2147483648:
        raise SceneError("scene.toml: [sampling] diagnostic_bytes must be 0..2147483648")

    materials = raw.get("materials", {})
    if not isinstance(materials, dict) or not materials:
        raise SceneError("scene.toml: [materials.<name>] needs at least one material")
    scene["materials"] = {}
    for name, spec in materials.items():
        scene["materials"][name] = _validate_material(name, spec)

    raw_components = raw.get("components", [])
    if not isinstance(raw_components, list) or not raw_components:
        raise SceneError("scene.toml: [[components]] needs at least one component")
    scene["components"] = [_validate_component(i, c) for i, c in enumerate(raw_components)]
    return scene


def _validate_material(name: str, spec: Any) -> dict:
    where = f"materials.{name}"
    if not isinstance(spec, dict):
        raise SceneError(f"scene.toml: [{where}] must be a table")
    preset = _field(where, spec, "preset", str, required=True)
    if preset not in materials_catalog():
        raise SceneError(
            f"scene.toml: [{where}] preset={preset!r} is not in catalog/materials.toml"
        )
    known = {"preset", "color", "tangent", "emission_color", *_MATERIAL_PARAMS}
    unknown = sorted(set(spec) - known)
    if unknown:
        raise SceneError(
            f"scene.toml: [{where}] unknown field {unknown[0]!r}; known: {', '.join(sorted(known))}"
        )
    color = _field(where, spec, "color", str, None)
    if color is not None and not _HEX.fullmatch(color):
        raise SceneError(f"scene.toml: [{where}] color={color!r} must be #RRGGBB")
    out = {"preset": preset, "color": color}
    emission = _field(where, spec, "emission_color", str, None)
    if emission is not None:
        if not _HEX.fullmatch(emission):
            raise SceneError(f"scene.toml: [{where}] emission_color={emission!r} must be #RRGGBB")
        out["emission_color"] = emission
    for key in _MATERIAL_PARAMS:
        if key == "texture":
            value = _field(where, spec, key, None)
            if value is not None and not isinstance(value, str):
                raise SceneError(f"scene.toml: [{where}] texture must be a recipe name")
            out[key] = value
        elif key in spec:
            out[key] = _num(where, spec, key, lo=0.0)
    if "tangent" in spec:
        tangent = spec["tangent"]
        if (
            not isinstance(tangent, list)
            or len(tangent) != 3
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in tangent)
            or not any(tangent)
        ):
            raise SceneError(f"scene.toml: [{where}] tangent must be a finite nonzero 3D vector")
        out["tangent"] = tangent
    return out


def _validate_component(index: int, comp: Any) -> dict:
    where = f"components[{index}]"
    if not isinstance(comp, dict):
        raise SceneError(f"scene.toml: [{where}] must be a table")
    kind = _field(where, comp, "kind", str, required=True)
    if kind not in COMPONENT_KINDS:
        raise SceneError(
            f"scene.toml: [{where}] kind={kind!r} must be one of {'|'.join(COMPONENT_KINDS)}"
        )
    out: dict[str, Any] = {"kind": kind}
    out["name"] = _field(where, comp, "name", str, f"{kind}_{index}")
    if kind != "bpy":
        out["material"] = _field(where, comp, "material", str, required=True)
    else:
        out["material"] = _field(where, comp, "material", str, None)
    for key, value in comp.items():
        if key in ("kind", "name", "material"):
            continue
        out[key] = value
    _check_kind_fields(where, out)
    return out


def _check_kind_fields(where: str, comp: dict) -> None:
    kind = comp["kind"]
    scalar = {k: v for k, v in comp.items() if k not in ("kind", "name", "material")}
    nums = (
        "radius",
        "thickness",
        "top",
        "depth",
        "height",
        "base",
        "major",
        "minor",
        "cap_height",
        "extrude",
        "puff",
        "step",
        "slab",
        "cube",
        "bevel",
        "z",
        "length",
        "width",
        "phase",
        "angle_deg",
        "edge_amount",
        "size_v",
        "seed",
        "scale",
        "energy",
        "height_scale",
    )
    for key in nums:
        if key in scalar and (
            isinstance(scalar[key], bool) or not isinstance(scalar[key], (int, float))
        ):
            raise SceneError(f"scene.toml: [{where}] {key}={scalar[key]!r} must be a number")
        if key in scalar and not math.isfinite(scalar[key]):
            raise SceneError(f"scene.toml: [{where}] {key}={scalar[key]!r} must be finite")
        if key in ("radius", "major", "minor") and key in scalar and scalar[key] <= 0:
            raise SceneError(f"scene.toml: [{where}] {key}={scalar[key]!r} must be > 0")
    if "smooth" in comp and type(comp["smooth"]) is not bool:
        raise SceneError(f"scene.toml: [{where}] smooth must be a boolean")
    if kind == "ring_text":
        for key in ("text", "font"):
            if not comp.get(key):
                raise SceneError(
                    f"scene.toml: [{where}] ring_text needs {key!r} "
                    f"(from_treatment leaves it blank for the agent to fill)"
                )
    if kind == "mesh" and not comp.get("path"):
        raise SceneError(f"scene.toml: [{where}] mesh needs a path to an OBJ/STL/PLY/GLB file")
    if kind == "cad" and comp.get("op", "box") not in ("box", "rounded_box", "cylinder"):
        raise SceneError(f"scene.toml: [{where}] cad op must be box|rounded_box|cylinder")
    if kind == "lathe":
        profile = comp.get("profile")
        if (
            not isinstance(profile, list)
            or len(profile) < 3
            or any(
                not isinstance(point, list)
                or len(point) != 2
                or any(
                    type(value) not in (int, float) or not math.isfinite(value) for value in point
                )
                or point[0] < 0
                for point in profile
            )
        ):
            raise SceneError(f"scene.toml: [{where}] lathe needs at least three [radius, z] points")
        sections = comp.get("sections", 96)
        if type(sections) is not int or not 16 <= sections <= 256:
            raise SceneError(f"scene.toml: [{where}] lathe sections must be an integer in 16..256")
    if kind == "plate" and comp.get("edge", "smooth") not in ("smooth", "irregular"):
        raise SceneError(f"scene.toml: [{where}] plate edge must be smooth|irregular")
    if kind == "relief" and comp.get("mode", "raise") not in ("raise", "cut", "through"):
        raise SceneError(f"scene.toml: [{where}] relief mode must be raise|cut|through")
    if kind in ("recess",) and "radius" not in comp and "layers" not in comp:
        raise SceneError(
            f"scene.toml: [{where}] recess needs radius (round pocket) "
            "or layers (motif-shaped pocket)"
        )


# ---------------------------------------------------------------------------
# from_treatment
# ---------------------------------------------------------------------------


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[ " + ", ".join(_toml_value(v) for v in value) + " ]"
    raise SceneError(f"cannot emit TOML for {value!r}")


MARK_KINDS = ("relief", "extrude", "inflate", "tube", "voxels", "layers")
ROLE_ORDER = ("primary", "secondary", "accent", "highlight", "ink")
# Per-kind vertical params that scale with the motif layer height.
HEIGHT_KEYS = {
    "relief": ("height",),
    "extrude": ("depth",),
    "inflate": ("puff",),
    "voxels": ("height",),
    "layers": ("step", "slab"),
}


def _load_motif_dict(motif_json: str | Path | dict) -> dict:
    """A motif path or parsed motif to a dict (SceneError on anything unreadable)."""
    if isinstance(motif_json, dict):
        return motif_json
    try:
        return json.loads(Path(motif_json).read_text())
    except Exception as exc:
        raise SceneError(f"motif_json {motif_json!r} is not readable JSON: {exc}") from exc


def _motif_role_groups(motif: dict) -> list[dict]:
    """Group motif layers by role: [{role, ids, fill, height}]. Height-0 and
    contour-less layers are skipped; `height` is the group's max layer height."""
    layers = motif.get("layers", []) if isinstance(motif, dict) else []
    groups: dict[str, dict] = {}
    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            continue
        role = layer.get("role", "primary")
        if role not in ROLE_ORDER:
            continue
        try:
            height = float(layer.get("height", 1.0))
        except (TypeError, ValueError) as err:
            raise SceneError(f"motif layer {layer.get('id', i)!r} height must be a number") from err
        contours = layer.get("contours", [])
        if height == 0 or not contours:
            continue
        lid = layer.get("id", f"layer_{i}")
        group = groups.setdefault(role, {"role": role, "ids": [], "fill": None, "height": 1.0})
        group["ids"].append(lid)
        if group["fill"] is None:
            fill = layer.get("fill")
            group["fill"] = fill if isinstance(fill, str) else None
        group["height"] = max(group["height"], height)
    return [groups[role] for role in ROLE_ORDER if role in groups]


def from_treatment(
    treatment_id: str,
    *,
    motif_json: str | Path | dict,
    palette: dict[str, str],
    material_id: str,
    seed: int,
) -> str:
    """Emit a starting scene.toml from a catalog preset; the agent then edits it.

    Layer-aware: one `[materials.<role>]` per motif role present (primary,
    secondary, accent, highlight, ink; preset `material_id`, color from the
    layer fill), and each mark component (relief/extrude/inflate/tube/voxels/
    layers) is emitted once per role with `layers = [<ids>]`, `material =
    <role>`, and vertical params scaled by the group's max layer height.
    Plates, rims, recesses, and ring text keep the `surface` material, colored
    from palette background (else primary). `[meta].concept` stays one line the
    caller can rewrite.
    """
    treatments = treatments_catalog()
    if treatment_id not in treatments:
        raise SceneError(f"unknown treatment {treatment_id!r}")
    if material_id not in materials_catalog():
        raise SceneError(f"unknown material {material_id!r}")
    motif = _load_motif_dict(motif_json)
    groups = _motif_role_groups(motif)
    palette = palette if isinstance(palette, dict) else {}
    preset = treatments[treatment_id].params
    lines = [
        "[meta]",
        f"concept = {json.dumps(f'custom|{treatment_id}|{material_id}')}",
        f"treatment = {json.dumps(treatment_id)}",
        f"seed = {seed}",
        "",
        "[camera]",
        f"tilt_deg = {preset.get('camera_tilt', 28.0)}",
        "lens_mm = 100.0",
        "framing = 0.84",
        "",
        "[mark]",
        f"scale = {preset.get('mark_scale', 1.0)}",
        "",
        "[lighting]",
        f"rig = {json.dumps(preset.get('lighting_rig', 'studio_soft'))}",
        'hdri = "polyhaven:poly_haven_studio"',
        "hdri_strength = 0.45",
        "",
        "[render]",
        'renderer = "cycles"',
        f"look = {json.dumps(preset.get('look', 'photoreal'))}",
        "glare = 0.0",
        "dof_fstop = 0.0",
        "",
        "[materials.surface]",
        f"preset = {json.dumps(material_id)}",
    ]
    surface_color = palette.get("background", palette.get("primary"))
    if surface_color:
        lines.append(f"color = {json.dumps(surface_color)}")
    for group in groups:
        lines += ["", f"[materials.{group['role']}]", f"preset = {json.dumps(material_id)}"]
        fill = group["fill"] or palette.get(group["role"])
        if fill:
            lines.append(f"color = {json.dumps(fill)}")
    for comp in preset.get("components", []):
        targets = [None]
        if comp.get("kind") in MARK_KINDS and groups:
            targets = groups
        for target in targets:
            lines += ["", "[[components]]"]
            for key, value in comp.items():
                if target is not None and key in ("layers", "material"):
                    continue  # replaced by the role split below
                if target is not None and key in HEIGHT_KEYS.get(comp["kind"], ()):
                    value = round(value * target["height"], 4)
                lines.append(f"{key} = {_toml_value(value)}")
            if target is not None:
                lines.append(f"layers = {_toml_value(target['ids'])}")
                lines.append(f"material = {json.dumps(target['role'])}")
            if comp.get("kind") == "ring_text":
                lines.append('text = ""  # agent fills: legend wording for the ring')
                lines.append(
                    'font = ""  # agent fills: a brief font spec ("Family:wght=700") or a TTF path'
                )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# compile
# ---------------------------------------------------------------------------


def resolve_font(spec: str, concept_dir: Path) -> Path:
    """A ring_text font spec (Google Fonts spec, absolute TTF path, or concept-relative file) to a TTF path."""
    try:
        from logo_maker import fonts  # type: ignore[import-not-found]
    except ImportError:
        fonts = None  # type: ignore[assignment]
    else:
        with suppress(Exception):  # not a google-fonts spec; try it as a path below
            return Path(fonts.resolve(spec))
    candidate = Path(spec)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    local = concept_dir / spec
    if local.exists():
        return local
    raise SceneError(
        f"scene.toml: ring_text font={spec!r} not found; "
        "want a Google Fonts spec, an absolute TTF path, or a file under the concept folder"
    )


def font_advances(text: str, font_path: str) -> list[float]:
    """Per-character advances in em units (TwoDSlice's fonts wins when present)."""
    try:
        from logo_maker import fonts  # type: ignore[import-not-found]

        return fonts.advances(text, str(font_path))
    except ImportError:
        pass
    from fontTools.ttLib import TTFont

    font = TTFont(str(font_path))
    cmap = font.getBestCmap()
    if cmap is None:
        raise SceneError(f"scene.toml: font {font_path} has no usable cmap")
    upm = getattr(font["head"], "unitsPerEm", None)
    if upm is None:
        raise SceneError(f"scene.toml: font {font_path} has no units-per-em")
    out = []
    for ch in text:
        if ch == " ":
            name = cmap.get(ord(" "))
            out.append(font["hmtx"][name][0] / upm if name else 0.3)
        elif ord(ch) in cmap:
            out.append(font["hmtx"][cmap[ord(ch)]][0] / upm)
        else:
            out.append(0.5)
    return out


def _motif_layers(motif: dict, select: Any) -> list[list[list[float]]]:
    """Contours for a layer selection: `all`, a layer id, or a list of ids."""
    layers = motif.get("layers", [])
    if select in (None, "all"):
        wanted = None
    elif isinstance(select, str):
        wanted = {select}
    else:
        wanted = set(select)
    contours = []
    for layer in layers:
        if wanted is not None and layer.get("id") not in wanted:
            continue
        scale = float(layer.get("height", 1.0))
        if scale == 0:
            continue
        contours.extend(layer.get("contours", []))
    if not contours:
        raise SceneError(f"motif has no contours for layers={select!r}")
    return contours


def _mark_layer(motif: dict) -> Any:
    """Default mark selection: every role group id (height-0 and empty layers
    already skipped); role-less motifs keep the old topmost-layer rule."""
    groups = _motif_role_groups(motif)
    if groups:
        return [lid for group in groups for lid in group["ids"]]
    layers = motif.get("layers", [])
    if len(layers) <= 1:
        return "all"
    last = layers[-1].get("id")
    return last if last is not None else "all"


def _selected_layers(motif: dict, select: Any) -> list[list[list[list[float]]]]:
    """One contour list per selected motif layer; each layer becomes its own solid."""
    layers = motif.get("layers", [])
    if select in (None, "all"):
        wanted = None
    elif isinstance(select, str):
        wanted = {select}
    else:
        wanted = set(select)
    groups = []
    for layer in layers:
        if wanted is not None and layer.get("id") not in wanted:
            continue
        if float(layer.get("height", 1.0)) == 0:
            continue
        contours = layer.get("contours", [])
        if contours:
            groups.append(contours)
    if not groups:
        raise SceneError(f"motif has no contours for layers={select!r}")
    return groups


def _union_all(solids: list[trimesh.Trimesh], name: str) -> trimesh.Trimesh:
    """Manifold union of per-layer solids into one watertight mesh."""
    if len(solids) == 1:
        return solids[0]
    mesh = solids[0]
    for other in solids[1:]:
        mesh = geometry.boolean_mesh(mesh, other, "union")
    import trimesh

    if isinstance(mesh, trimesh.Trimesh) and not mesh.is_watertight:
        raise SceneError(f"scene.toml: [{name}] layer union is not watertight")
    return mesh


def _scale_motif(motif: dict, scale: float) -> dict:
    """Shrink or grow every motif contour about the viewBox center (500, 500)."""
    if scale == 1.0:
        return motif
    layers = [
        {
            **layer,
            "contours": [
                [[500.0 + (x - 500.0) * scale, 500.0 + (y - 500.0) * scale] for x, y in contour]
                for contour in layer.get("contours", [])
            ],
        }
        for layer in motif.get("layers", [])
    ]
    return {**motif, "layers": layers}


def compile(concept_dir: Path | str, quality: str, on_asset: Any | None = None) -> Path:
    """Compile scene.toml + motif.json to `.build/scene.json` with host-built meshes."""
    from logo_maker import hdri as hdri_mod

    if quality not in QUALITY:
        raise SceneError(f"unknown quality {quality!r}; want test|preview|final")
    concept_dir = Path(concept_dir)
    scene = load_scene(concept_dir / "scene.toml")
    motif_path = concept_dir / "motif.json"
    if not motif_path.exists():
        raise SceneError(f"{concept_dir} has no motif.json; run the 2D stage first")
    motif = _scale_motif(json.loads(motif_path.read_text()), scene["mark"]["scale"])

    build_dir = concept_dir / BUILD_DIRNAME
    mesh_dir = build_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    lighting_entry = lighting_catalog()[scene["lighting"]["rig"]]
    hdri_spec = scene["lighting"]["hdri"]
    hdri_path = hdri_mod.fetch(hdri_spec, on_asset=on_asset) if hdri_spec else None

    materials = {}
    for name, spec in scene["materials"].items():
        params = dict(materials_catalog()[spec["preset"]].params)
        for key, value in spec.items():
            if key not in ("preset", "color") and value is not None:
                params[key] = value
        base = spec.get("color") or params.pop("base_color", "#FFFFFF")
        materials[name] = _resolve_material(name, spec["preset"], base, params)

    objects: list[dict] = []
    plates: dict[str, dict] = {}  # name -> plate spec (rebuilt when cuts land)
    cuts: list[dict] = []  # recess + cut/through relief, applied to plates after pass 1
    for comp in scene["components"]:
        kind = comp["kind"]
        if kind == "plate":
            plates[comp["name"]] = comp
        elif kind == "recess" or (kind == "relief" and comp.get("mode", "raise") != "raise"):
            cuts.append(comp)
        elif kind == "bpy":
            objects.append(
                {
                    "name": comp["name"],
                    "kind": "bpy",
                    "material": None,
                    "mesh": None,
                    "params": {
                        k: v for k, v in comp.items() if k not in ("kind", "name", "material")
                    },
                }
            )
        else:
            objects.append(_build_object(comp, scene, motif, concept_dir, mesh_dir))

    for plate_name, plate in plates.items():
        holes = _plate_holes(plate_name, cuts, motif)
        mesh = _build_plate(plate, holes)
        filename = f"{plate_name}.ply"
        geometry.save_ply(mesh, mesh_dir / filename)
        objects.append(
            {
                "name": plate_name,
                "kind": "plate",
                "material": plate["material"],
                "mesh": f"meshes/{filename}",
                "params": {k: v for k, v in plate.items() if k not in ("kind", "name", "material")},
            }
        )
    for cut in cuts:
        for obj in _build_cut(cut, scene, motif, mesh_dir):
            objects.append(obj)

    quality_spec = sampling_quality(scene, quality)
    quality_spec["exposure"] = scene["render"]["exposure"]

    scene_json = {
        "meta": scene["meta"],
        "quality": quality_spec,
        "sampling": scene["sampling"],
        "camera": scene["camera"],
        "lighting": {
            "rig": scene["lighting"]["rig"],
            "rig_params": lighting_entry.params,
            "hdri": str(hdri_path) if hdri_path else None,
            "hdri_strength": scene["lighting"]["hdri_strength"],
        },
        "render": scene["render"],
        "materials": materials,
        "motif": motif,
        "objects": objects,
    }
    out = build_dir / "scene.json"
    out.write_text(json.dumps(scene_json, indent=2))
    return out


def sampling_quality(scene: dict, quality: str) -> dict:
    """Resolve effective controls without losing explicit false/zero overrides."""
    from logo_maker.sampling import Settings, validate_settings

    spec = {"name": quality, **QUALITY[quality], "min_samples": 0, "seed": scene["meta"]["seed"]}
    overrides = {
        k: v
        for k, v in scene["render"].items()
        if k in {"max_samples", "adaptive_threshold", "min_samples", "seed", "adaptive"}
        and v is not None
    }
    if "max_samples" in overrides or "adaptive_threshold" in overrides:
        spec["adaptive"] = True
    for name, value in overrides.items():
        key = "samples" if name == "max_samples" else name
        spec[key] = int(value) if key in {"samples", "min_samples", "seed"} else value
    spec["overrides"] = overrides
    try:
        validate_settings(Settings.from_quality(spec))
    except ValueError as exc:
        raise SceneError(f"scene.toml: [render] {exc}") from exc
    return spec


def _resolve_material(name: str, preset: str, base_hex: str, params: dict) -> dict:
    base = geometry.hex_to_linear(base_hex)
    emission_hex = params.get("emission_color", base_hex)
    return {
        "preset": preset,
        "base_color_linear": list(base),
        "metallic": float(params.get("metallic", 0.0)),
        "roughness": float(params.get("roughness", 0.5)),
        "coat": float(params.get("coat", params.get("coat_weight", 0.0))),
        "coat_roughness": float(params.get("coat_roughness", 0.2)),
        "subsurface": float(params.get("subsurface", params.get("sss", 0.0))),
        "sheen": float(params.get("sheen", 0.0)),
        "transmission": float(params.get("transmission", 0.0)),
        "ior": float(params.get("ior", 1.45)),
        "emission_linear": list(geometry.hex_to_linear(emission_hex)),
        "emission_strength": float(params.get("emission_strength", 0.0)),
        "anisotropy": float(params.get("anisotropy", 0.0)),
        **({"tangent": params["tangent"]} if "tangent" in params else {}),
        "texture": params.get("texture", "none") or "none",
        "bump": float(params.get("bump", 0.0)),
        "bump_scale": float(params.get("bump_scale", 40.0)),
    }


def _target_top(comp: dict, scene: dict) -> float:
    """The plate surface this component sits on (explicit `top` wins)."""
    if comp.get("top") is not None:
        return float(comp["top"])
    target = comp.get("target")
    for other in scene["components"]:
        if other["kind"] == "plate" and (target is None or other["name"] == target):
            return float(other.get("top", 0.17))
    return 0.17


def _plate_holes(plate_name: str, cuts: list[dict], motif: dict) -> list[list[tuple]]:
    holes: list[list[tuple]] = []
    for cut in cuts:
        if cut.get("target", None) not in (None, plate_name):
            continue
        if cut["kind"] == "recess" and "radius" in cut:
            holes.append(_circle_poly(float(cut["radius"])))
        elif "layers" in cut or cut.get("kind") == "relief":
            default = _mark_layer(motif) if cut.get("kind") == "relief" else "all"
            for contour in _motif_layers(motif, cut.get("layers", default)):
                holes.append([geometry.to3(x, y) for x, y in contour])
    return holes


def _circle_poly(radius: float, segments: int = 128) -> list[tuple]:
    import math

    return [
        (
            radius * math.cos(2 * math.pi * i / segments),
            radius * math.sin(2 * math.pi * i / segments),
        )
        for i in range(segments)
    ]


def _build_plate(plate: dict, holes: list[list[tuple]]):
    return geometry.plate_mesh(
        radius=float(plate.get("radius", 1.0)),
        thickness=float(plate.get("thickness", 0.17)),
        top_z=float(plate.get("top", 0.17)),
        edge=plate.get("edge", "smooth"),
        seed=int(plate.get("seed", 0)),
        holes=holes or None,
    )


def _build_object(comp: dict, scene: dict, motif: dict, concept_dir: Path, mesh_dir: Path) -> dict:
    kind = comp["kind"]
    name = comp["name"]
    top = _target_top(comp, scene)
    mesh = None
    if kind == "rim":
        mesh = geometry.rim_mesh(
            major=float(comp.get("major", 0.85)),
            minor=float(comp.get("minor", 0.03)),
            z=float(comp.get("z", top)),
        )
    elif kind == "relief":
        groups = _selected_layers(motif, comp.get("layers", _mark_layer(motif)))
        height = float(comp.get("height", 0.03)) * float(comp.get("height_scale", 1.0))
        base = float(comp.get("base", top - 0.002))
        mesh = _union_all([geometry.relief_mesh(g, height, base) for g in groups], name)
    elif kind == "extrude":
        groups = _selected_layers(motif, comp.get("layers", _mark_layer(motif)))
        depth = float(comp.get("depth", 0.22)) * float(comp.get("height_scale", 1.0))
        base = float(comp.get("base", 0.0))
        mesh = _union_all([geometry.relief_mesh(g, depth, base) for g in groups], name)
    elif kind == "inflate":
        contours = _motif_layers(motif, comp.get("layers", "all"))
        mesh = geometry.inflate_mesh(
            contours,
            puff=float(comp.get("puff", 0.16)) * float(comp.get("height_scale", 1.0)),
            base_z=float(comp.get("base", 0.0)),
            depth=float(comp.get("depth", 0.05)),
        )
    elif kind == "layers":
        mesh = _build_layers(comp, motif)
    elif kind == "ring_text":
        font_path = resolve_font(comp["font"], concept_dir)
        mesh = geometry.ring_text_mesh(
            str(font_path),
            comp["text"],
            radius=float(comp.get("radius", 0.7)),
            cap_height=float(comp.get("cap_height", 0.07)),
            base_z=float(comp.get("base", top)),
            extrude=float(comp.get("extrude", 0.012)),
        )
    elif kind == "ribbon":
        mesh = geometry.ribbon_mesh(
            angle_deg=float(comp.get("angle_deg", 0.0)),
            length=float(comp.get("length", 3.2)),
            width=float(comp.get("width", 0.4)),
            z=float(comp.get("z", -0.02)),
            phase=float(comp.get("phase", 0.0)),
            thickness=float(comp.get("thickness", 0.012)),
        )
    elif kind == "tube":
        groups = _selected_layers(motif, comp.get("layers", _mark_layer(motif)))
        contours = [c for group in groups for c in group]
        mesh = geometry.tube_mesh(
            [[geometry.to3(x, y) for x, y in c] for c in contours],
            radius=float(comp.get("radius", 0.035)),
            z=float(comp.get("z", 0.1)),
        )
    elif kind == "voxels":
        contours = _motif_layers(motif, comp.get("layers", "all"))
        mesh = geometry.voxel_mesh(
            contours,
            cube=float(comp.get("cube", 0.07)),
            height=float(comp.get("height", 0.14)),
            base_z=float(comp.get("base", 0.0)),
        )
    elif kind == "cad":
        spec = {"op": comp.get("op", "box")}
        for key in ("size", "radius", "height", "center"):
            if key in comp:
                spec[key] = comp[key]
        mesh = geometry.cad_mesh(spec)
    elif kind == "lathe":
        try:
            mesh = geometry.lathe_mesh(comp["profile"], comp.get("sections", 96))
        except ValueError as exc:
            raise SceneError(f"scene.toml: [{name}] {exc}") from exc
    elif kind == "mesh":
        src = Path(comp["path"])
        if not src.is_absolute():
            src = concept_dir / src
        if not src.exists():
            raise SceneError(f"scene.toml: mesh {name!r} path={comp['path']!r} does not exist")
        import trimesh

        loaded = trimesh.load(src, force="mesh")
        if not isinstance(loaded, trimesh.Trimesh):
            raise SceneError(f"scene.toml: mesh {name!r} path={comp['path']!r} is not a mesh")
        scale = float(comp.get("scale", 1.0))
        if scale != 1.0:
            loaded.apply_scale(scale)
        loc = comp.get("location", [0.0, 0.0, 0.0])
        loaded.apply_translation(tuple(float(v) for v in loc))
        mesh = loaded
    else:
        raise SceneError(f"scene.toml: [{name}] kind={kind!r} is not built host-side")
    filename = f"{name}.ply"
    geometry.save_ply(mesh, mesh_dir / filename)
    return {
        "name": name,
        "kind": kind,
        "material": comp.get("material"),
        "mesh": f"meshes/{filename}",
        "params": {k: v for k, v in comp.items() if k not in ("kind", "name", "material")},
    }


def _build_layers(comp: dict, motif: dict):
    """One slab per data-layer value, stacked with `step` between slab bases."""
    base = float(comp.get("base", 0.0))
    step = float(comp.get("step", 0.05)) * float(comp.get("height_scale", 1.0))
    slab = float(comp.get("slab", 0.05)) * float(comp.get("height_scale", 1.0))
    groups: dict[Any, list] = {}
    for layer in motif.get("layers", []):
        groups.setdefault(layer.get("layer", 0), []).extend(layer.get("contours", []))
    if not groups:
        raise SceneError("scene.toml: layers needs motif layers with data-layer values")
    import trimesh

    parts = []
    for i, key in enumerate(sorted(groups)):
        contours = groups[key]
        if not contours:
            continue
        z0 = base + i * step
        parts.append(geometry.relief_mesh(contours, slab, z0))
    if not parts:
        raise SceneError("scene.toml: layers found no non-empty motif layers")
    return trimesh.util.concatenate(parts)


def _build_cut(cut: dict, scene: dict, motif: dict, mesh_dir: Path) -> list[dict]:
    """Pocket lining for a recess or a cut/through relief: floor slab + lip tube."""
    top = _target_top(cut, scene)
    name = cut["name"]
    if "radius" in cut:
        contours = [_circle_poly(float(cut["radius"]))]
    else:
        raw = _motif_layers(motif, cut.get("layers", "all"))
        contours = [[geometry.to3(x, y) for x, y in c] for c in raw]
    through = cut.get("mode") == "through"
    depth = float(cut.get("depth", top if through else 0.06))
    floor_z = top - depth
    import trimesh

    parts: list[trimesh.Trimesh] = []
    if not through:
        parts.append(geometry._extrude(contours, floor_z - 0.004, floor_z))
    lip_z = top if cut["kind"] == "recess" else top - 0.001
    parts.append(geometry.tube_mesh(contours, radius=0.006, z=lip_z, sides=8))
    mesh = trimesh.util.concatenate(parts)
    if not isinstance(mesh, trimesh.Trimesh):
        raise SceneError(f"scene.toml: [{name}] lining is not a mesh")
    filename = f"{name}_lining.ply"
    geometry.save_ply(mesh, mesh_dir / filename)
    params = {k: v for k, v in cut.items() if k not in ("kind", "name", "material")}
    return [
        {
            "name": f"{name}_lining",
            "kind": "recess_lining",
            "material": cut.get("material"),
            "mesh": f"meshes/{filename}",
            "params": params,
        }
    ]
