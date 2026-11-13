"""Owned Metal worker for packed scenes and alternate inspection views."""

from __future__ import annotations

import json
import math
import platform
from pathlib import Path

from logo_maker.blender.execution import render_verified
from logo_maker.host import serve


def _open_scene(source: Path, compiled: bool):
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
    import bpy

    from logo_maker.blender.settings import apply_cycles_gpu

    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("3D studies require Apple Silicon macOS")
    source, output = Path(payload["source"]), Path(payload["output"])
    compiled = payload["compiled"]
    scene = _open_scene(source, compiled)
    apply_cycles_gpu()
    bpy.context.view_layer.update()
    _render_settings(scene, payload["resolution"], payload["samples"])
    name = payload["view"]
    if name in {"front", "grazing", "rear", "underside"}:
        _angle(scene, name, _corners(scene))
    if name == "independent-seed":
        scene.cycles.seed = (scene.cycles.seed + 42017) % 2147483647
    if name == "lower-threshold":
        scene.cycles.adaptive_threshold = 0.004
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
    diagnostics = report.get("diagnostics", {})
    if diagnostics.get("status") == "retained":
        diagnostics["path"] = Path(diagnostics["path"]).name
        evidence.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    serve(render)
