"""Build entry: `python -m logo_maker.blender.build <scene.json>`.

Builds the compiled scene in bpy, renders the PNG (RGBA, transparent film),
saves scene.blend, exports model.glb, and — for non-Cycles renderers — writes
meshes/ + meshes/scene_export.json for the alternate renderer. Prints the PNG,
blend, and glb paths, one per line.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from logo_maker.geometry import camera_distance, fov_from_lens


def main(scene_json: str) -> None:
    import bpy

    from logo_maker.blender import components, lighting, materials, settings

    scene_path = Path(scene_json)
    build_dir = scene_path.parent
    concept_dir = build_dir.parent
    scene = json.loads(scene_path.read_text())

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    look = scene["render"].get("look", "photoreal")
    mats = {
        name: materials.make_material(f"mat_{name}", spec, look)
        for name, spec in scene["materials"].items()
    }

    light = scene["lighting"]
    lighting.apply_lighting(light["rig_params"], light["hdri"], light["hdri_strength"])

    visible = components.build_objects(scene, build_dir, mats)
    _frame_camera(scene, visible)
    components.setup_outlines(look, visible)
    components.setup_compositor(
        float(scene["render"].get("glare", 0.0)), float(scene["render"].get("dof_fstop", 0.0))
    )

    settings.apply_cycles_gpu()
    settings.apply_quality(scene["quality"])

    png = concept_dir / f"{scene['quality']['name']}.png"
    bpy.context.scene.render.filepath = str(png)
    bpy.ops.render.render(write_still=True)

    blend = concept_dir / "scene.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    glb = concept_dir / "model.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(glb), export_format="GLB", use_selection=False, export_yup=True
    )

    if scene["render"].get("renderer", "cycles") != "cycles":
        _write_export(scene, visible, build_dir, concept_dir)

    print(str(png))
    print(str(blend))
    print(str(glb))


def _frame_camera(scene: dict, visible: list) -> None:
    """Place the camera so the bounds of everything visible fill `framing`."""
    import bpy
    import mathutils

    cam_data = bpy.data.cameras.new("LogoCam")
    cam_obj = bpy.data.objects.new("LogoCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    cfg = scene["camera"]
    lens = float(cfg.get("lens_mm", 100.0))
    cam_data.lens = lens
    sensor = float(cfg.get("sensor_mm", 36.0))
    fov = fov_from_lens(lens, sensor)

    corners = []
    for obj in visible:
        if getattr(obj, "hide_render", False):
            continue
        corners.extend(obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box)
    if not corners:
        center = mathutils.Vector((0, 0, 0.1))
        distance = camera_distance(1.0, fov, float(cfg.get("framing", 0.84)))
    else:
        from logo_maker.geometry import frame_distance

        xs = [c.x for c in corners]
        ys = [c.y for c in corners]
        zs = [c.z for c in corners]
        center = mathutils.Vector(
            ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
        )
        offsets = [
            (x - center.x, y - center.y, z - center.z) for x, y, z in zip(xs, ys, zs, strict=True)
        ]
        tilt = math.radians(float(cfg.get("tilt_deg", 28.0)))
        azim = math.radians(float(cfg.get("azimuth_deg", 0.0)))
        width = float(scene["render"].get("width", 1000))
        height = float(scene["render"].get("height", 1000))
        distance = frame_distance(
            offsets, tilt, azim, fov, float(cfg.get("framing", 0.84)), width / max(height, 1.0)
        )
    tilt = math.radians(float(cfg.get("tilt_deg", 28.0)))
    azim = math.radians(float(cfg.get("azimuth_deg", 0.0)))
    # tilt is measured from straight-on (looking down the plate normal +Z)
    direction = mathutils.Vector(
        (math.sin(azim) * math.sin(tilt), -math.cos(azim) * math.sin(tilt), math.cos(tilt))
    )
    cam_obj.location = center + direction * distance
    cam_obj.rotation_euler = (center - cam_obj.location).to_track_quat("-Z", "Y").to_euler()
    cam_data.clip_start = distance / 100.0
    cam_data.clip_end = distance * 100.0
    cam_data.dof.focus_distance = distance


def _write_export(scene: dict, visible: list, build_dir: Path, concept_dir: Path) -> Path:
    """World-space triangulated PLYs plus the renderer-neutral scene description."""
    import bpy
    import mathutils
    import numpy as np
    import trimesh

    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh_dir = concept_dir / "meshes"
    mesh_dir.mkdir(exist_ok=True)
    objects = []
    for obj in visible:
        if getattr(obj, "hide_render", False) or obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        verts = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", verts)
        world = np.array(obj.matrix_world, dtype=np.float64)
        verts = verts.reshape(-1, 3) @ world[:3, :3].T + world[:3, 3]
        mesh.calc_loop_triangles()
        tris = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
        mesh.loop_triangles.foreach_get("vertices", tris)
        evaluated.to_mesh_clear()
        tri = trimesh.Trimesh(vertices=verts, faces=tris.reshape(-1, 3), process=True)
        filename = f"{obj.name}.ply"
        tri.export(mesh_dir / filename)
        objects.append(
            {"name": obj.name, "mesh": f"meshes/{filename}", "material": _material_of(obj, scene)}
        )
    rig = scene["lighting"]["rig_params"]
    lights = [
        {
            "name": item.get("name", "Light"),
            "type": item.get("type", "area"),
            "location": list(item.get("location", (0, 0, 5))),
            "target": list(item.get("target", (0, 0, 0))),
            "size": float(item.get("size", 3.0)),
            "power_w": float(item.get("energy", item.get("power_w", 100.0))),
            "color_linear": [1.0, 1.0, 1.0, 1.0],
        }
        for item in rig.get("lights", [])
    ]
    cam = bpy.context.scene.camera
    forward = cam.matrix_world.to_quaternion() @ mathutils.Vector((0, 0, -1))
    target = cam.matrix_world.to_translation() + forward * cam.data.dof.focus_distance
    export = {
        "resolution": [
            bpy.context.scene.render.resolution_x,
            bpy.context.scene.render.resolution_y,
        ],
        "camera": {
            "location": list(cam.matrix_world.to_translation()),
            "target": [target.x, target.y, target.z],
            "up": [0.0, 0.0, 1.0],
            "fov_deg": math.degrees(
                fov_from_lens(cam.data.lens, float(scene["camera"].get("sensor_mm", 36.0)))
            ),
            "lens_mm": cam.data.lens,
            "sensor_mm": float(scene["camera"].get("sensor_mm", 36.0)),
        },
        "world": {
            "hdri": scene["lighting"]["hdri"],
            "strength": scene["lighting"]["hdri_strength"],
            "color_linear": [0.97, 0.96, 0.94, 1.0],
            "transparent": True,
        },
        "lights": lights,
        "objects": objects,
        "materials": {
            name: {
                k: (list(v) if isinstance(v, (list, tuple)) else v)
                for k, v in spec.items()
                if k != "preset"
            }
            for name, spec in scene["materials"].items()
        },
        "glb": "model.glb",
    }
    out = mesh_dir / "scene_export.json"
    out.write_text(json.dumps(export, indent=2))
    return out


def _material_of(obj, scene: dict) -> str | None:
    for entry in scene["objects"]:
        if entry["name"] == obj.name:
            return entry.get("material")
    return None


if __name__ == "__main__":
    main(sys.argv[-1])
