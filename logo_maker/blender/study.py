"""Owned Metal worker for packed scenes and alternate inspection views."""

from __future__ import annotations

import json
import math
from pathlib import Path

from logo_maker.blender.execution import render_verified
from logo_maker.blender.metal import require_metal_device
from logo_maker.host import serve


def _open_scene(source: Path, compiled: bool):
    require_metal_device()
    import bpy

    if compiled:
        from logo_maker.blender.build import prepare_scene

        spec = json.loads(source.read_text())
        if spec["render"]["renderer"] != "cycles":
            raise ValueError("3D studies require Cycles Metal on Apple Silicon")
        prepare_scene(spec, source.parent)
        bpy.ops.file.pack_all()
    else:
        bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    scene = bpy.context.scene
    if bpy.data.libraries:
        raise ValueError("make linked objects and libraries local before rendering a study")
    for block in bpy.data.texts:
        if block.use_module:
            raise ValueError("disable registered scripts in the packed scene")
    for collection in (bpy.data.objects, bpy.data.materials, bpy.data.node_groups, bpy.data.scenes):
        for block in collection:
            animation = getattr(block, "animation_data", None)
            if animation and animation.drivers:
                raise ValueError(f"bake drivers before packing the scene: {block.name}")
    for tree in [m.node_tree for m in bpy.data.materials if m.use_nodes] + list(
        bpy.data.node_groups
    ):
        if any(node.bl_idname == "ShaderNodeScript" for node in tree.nodes):
            raise ValueError("bake external shader scripts before packing the scene")
    for collection, internal in (
        (bpy.data.images, {"GENERATED", "VIEWER"}),
        (bpy.data.fonts, {"<builtin>"}),
        (bpy.data.sounds, set()),
    ):
        for data in collection:
            filepath = getattr(data, "filepath", "")
            if (
                filepath
                and filepath not in internal
                and getattr(data, "source", "") not in internal
                and not (getattr(data, "packed_file", None) or getattr(data, "packed_files", ()))
            ):
                raise ValueError(f"pack external data in the scene before rendering: {data.name}")
    if bpy.data.cache_files or bpy.data.volumes or bpy.data.movieclips:
        raise ValueError(
            "a study scene must use self-contained geometry, fonts and packed textures"
        )
    for image in bpy.data.images:
        if image.source in {"MOVIE", "SEQUENCE"}:
            raise ValueError(f"replace image sequence or movie with a packed still: {image.name}")
    if scene.render.use_sequencer and scene.sequence_editor and scene.sequence_editor.strips:
        raise ValueError("render the 3D scene directly with the sequencer disabled")
    if scene.camera is None or not _corners(scene):
        raise ValueError("the scene needs an active camera and visible geometry")
    return scene


def _campaign_static(scene) -> None:
    """Reject external or frame-dependent inputs from the packed campaign contract."""
    import bpy

    for obj in scene.objects:
        for modifier in obj.modifiers:
            if modifier.type in {
                "CLOTH",
                "FLUID",
                "DYNAMIC_PAINT",
                "OCEAN",
                "MESH_CACHE",
                "MESH_SEQUENCE_CACHE",
                "SOFT_BODY",
                "PARTICLE_SYSTEM",
            }:
                raise ValueError(f"apply dynamic or cached modifier {obj.name}/{modifier.name}")
    if scene.rigidbody_world:
        raise ValueError("apply rigid body transforms before saving the logo scene")
    trees = list(bpy.data.node_groups)
    trees.extend(
        block.node_tree
        for block in (*bpy.data.materials, *bpy.data.worlds, *bpy.data.lights, *bpy.data.scenes)
        if getattr(block, "node_tree", None)
    )
    for tree in trees:
        for node in tree.nodes:
            if node.bl_idname in {
                "GeometryNodeSimulationInput",
                "GeometryNodeBake",
                "ShaderNodeScript",
                "CompositorNodeMovieClip",
                "CompositorNodeImageSequence",
            }:
                raise ValueError(f"apply dynamic or external node {tree.name}/{node.name}")
            if node.bl_idname == "ShaderNodeTexIES" and node.mode == "EXTERNAL":
                raise ValueError(f"pack the IES profile {tree.name}/{node.name}")


def _corners(scene):
    import bpy
    from mathutils import Vector

    depsgraph = bpy.context.evaluated_depsgraph_get()
    return [
        instance.matrix_world @ Vector(corner)
        for instance in depsgraph.object_instances
        if instance.object.type in {"MESH", "CURVE", "SURFACE", "FONT", "META"}
        and not instance.object.hide_render
        for corner in instance.object.bound_box
    ]


def _angle(scene, kind, corners):
    import bpy
    from mathutils import Vector

    from logo_maker.geometry import fov_from_lens, frame_distance

    center = Vector(
        tuple((min(p[i] for p in corners) + max(p[i] for p in corners)) / 2 for i in range(3))
    )
    authored = scene.camera
    camera = authored.evaluated_get(bpy.context.evaluated_depsgraph_get())
    original = camera.matrix_world.translation - center
    azimuth = math.atan2(original.x, -original.y)
    tilt = math.atan2(math.hypot(original.x, original.y), original.z)
    tilt, delta = {
        "front": (tilt, 0),
        "grazing": (math.radians(76), math.radians(34)),
        "rear": (math.radians(76), math.pi),
        "underside": (math.radians(124), math.radians(-24)),
    }[kind]
    azimuth += delta
    direction = Vector(
        (math.sin(azimuth) * math.sin(tilt), -math.cos(azimuth) * math.sin(tilt), math.cos(tilt))
    )
    data = authored.data.copy()
    camera = bpy.data.objects.new("Study inspection camera", data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = "PERSP"
    camera.data.lens = 70
    camera.data.sensor_fit = "HORIZONTAL"
    camera.data.shift_x = camera.data.shift_y = 0
    camera.data.dof.use_dof = False
    distance = frame_distance(
        [tuple(p - center) for p in corners],
        tilt,
        azimuth,
        fov_from_lens(70, camera.data.sensor_width),
        0.79,
    )
    camera.location = center + direction * distance
    camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    camera.data.clip_start, camera.data.clip_end = distance / 1000, distance * 10


def _render_settings(scene, resolution, samples):
    scene.render.resolution_x = scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.use_border = False
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.008 if resolution == 2000 else 0.04
    scene.cycles.adaptive_min_samples = min(samples, 64 if resolution == 2000 else 16)
    scene.cycles.use_animated_seed = False
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_use_gpu = True
    scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"


def render(payload: dict) -> dict:
    if payload.get("operation") == "environment":
        from logo_maker.blender.profile import environment

        return environment()
    if payload.get("operation") == "inspect_packed_scene":
        scene = _open_scene(Path(payload["source"]), False)
        _campaign_static(scene)
        return {"camera": scene.camera.name, "editable_objects": len(scene.objects)}
    require_metal_device()

    import bpy

    from logo_maker.blender.settings import apply_cycles_gpu

    source, output = Path(payload["source"]), Path(payload["output"])
    compiled = payload["compiled"]
    scene = _open_scene(source, compiled)
    if payload.get("authored_cameras"):
        _campaign_static(scene)
    apply_cycles_gpu()
    bpy.context.view_layer.update()
    _render_settings(scene, payload["resolution"], payload["samples"])
    if "adaptive_threshold" in payload:
        scene.cycles.adaptive_threshold = payload["adaptive_threshold"]
        scene.cycles.adaptive_min_samples = payload.get("min_samples", 0)
    name = payload["view"]
    if name in {"front", "grazing", "rear", "underside"}:
        authored = bpy.data.objects.get(f"Study {name} camera")
        if payload.get("authored_cameras") and authored and authored.type == "CAMERA":
            scene.camera = authored
        else:
            _angle(scene, name, _corners(scene))
    if name == "independent-seed":
        scene.cycles.seed = (scene.cycles.seed + 42017) % 2147483647
    if name == "lower-threshold":
        scene.cycles.adaptive_threshold = payload.get("adaptive_threshold", 0.008) / 2
    if name == "degraded-threshold":
        scene.cycles.adaptive_threshold = 0.02
    png = output / f"{name}.png"
    inputs = {"source": source}
    if compiled:
        inputs.update(
            (file.relative_to(source.parent).as_posix(), file)
            for file in sorted((source.parent / "meshes").glob("*.ply"))
        )
    scene.render.filepath = "//hero-transparent.png" if name == "hero-transparent" else str(png)
    if name == "hero-transparent":
        blend = output / "scene.blend"
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
        inputs["editable_scene"] = blend
    evidence = output / f"{name}-execution.json"
    report = render_verified(
        png,
        evidence,
        inputs=inputs,
        diagnostic_bytes=400 * 1024**2 if payload.get("diagnostics") else 0,
    )
    report["scene_inventory"] = {
        "schema": 1,
        "contract": "packed-static-v1",
        "objects": [{"name": obj.name, "type": obj.type} for obj in scene.objects],
        "materials": [mat.name for mat in bpy.data.materials],
        "images": [{"name": im.name, "source": im.source} for im in bpy.data.images],
        "source_sha256": report["inputs_sha256"]["source"],
    }
    if payload.get("downsample"):
        from logo_maker.render import _downsample_final
        from logo_maker.sampling_diagnostics import sha256

        report["native_png_sha256"] = report["png_sha256"]
        _downsample_final(png)
        report["png_sha256"] = sha256(png)
        report["delivery_resolution"] = 2000
    diagnostics = report.get("diagnostics", {})
    if diagnostics.get("status") == "retained":
        diagnostics["path"] = Path(diagnostics["path"]).name
    evidence.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    serve(render)
