"""Inspect inherited CPU preferences and optionally render a real policy probe.

Usage: uv run --locked python scripts/validate_gpu.py [--baseline REV] [--render DIR]
The baseline is loaded in isolation from git without switching the working tree.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    import bpy

    from logo_maker.blender import settings
    from logo_maker.blender.execution import render_verified

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline")
    parser.add_argument("--render", type=Path)
    args = parser.parse_args()
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.refresh_devices()
    for device in prefs.devices:
        device.use = device.type == "CPU"  # inherited CPU on, Metal off
    print("Scenario: inherited CPU enabled, Metal disabled", flush=True)
    print("Revision:", args.baseline or "working tree", flush=True)
    print("Blender:", bpy.app.version_string, bpy.app.build_hash.decode(), flush=True)
    if args.baseline:
        if args.render:
            parser.error("baseline inspection does not render under an unenforced policy")
        code = subprocess.run(
            ["git", "show", f"{args.baseline}:logo_maker/blender/settings.py"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        with TemporaryDirectory(prefix="logo-gpu-baseline-") as tmp:
            source = Path(tmp) / "settings.py"
            source.write_text(code)
            spec = importlib.util.spec_from_file_location("baseline_settings", source)
            if spec is None or spec.loader is None:
                raise RuntimeError("could not load baseline settings module")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.apply_cycles_gpu()
    else:
        settings.apply_cycles_gpu()
    for device in prefs.devices:
        print(f"{device.type}: {device.name}; enabled={device.use}", flush=True)
    cpu_enabled = any(d.type == "CPU" and d.use for d in prefs.devices)
    print("CPU tracing disabled:", not cpu_enabled, flush=True)
    if args.render:
        args.render.mkdir(parents=True, exist_ok=False)
        settings.apply_quality({"resolution": 64, "samples": 4})
        bpy.ops.mesh.primitive_uv_sphere_add()
        bpy.ops.object.camera_add(location=(0, 0, 6))
        bpy.context.scene.camera = bpy.context.object
        # Reintroduce inherited CPU immediately before the actual rendering boundary.
        for device in prefs.devices:
            device.use = device.type == "CPU"
        report = render_verified(args.render / "probe.png", args.render / "execution.json")
        print("Runtime denoiser:", json.dumps(report["denoiser_effective"]), flush=True)
        print("Selected devices:", json.dumps(report["devices"]), flush=True)
        print("Render policy:", report["status"], flush=True)


if __name__ == "__main__":
    main()
