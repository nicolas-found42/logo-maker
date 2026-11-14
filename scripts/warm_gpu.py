"""Compile the Metal kernels once so later renders start immediately.

Runs one tiny GPU render through the real pipeline entry point. First runs take
1.5-5 minutes with no output while kernels compile; never kill this early.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCENE = """
from logo_maker.blender.metal import require_metal_device

require_metal_device()

import bpy

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(size=1.0)
cube = bpy.context.active_object
mat = bpy.data.materials.new("warm")
mat.use_nodes = True
cube.data.materials.append(mat)
cam_data = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_data)
cam.location = (2.5, -2.5, 2.0)
cam.rotation_euler = (1.1, 0.0, 0.785)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
sc = bpy.context.scene
sc.render.engine = "CYCLES"
cp = bpy.context.preferences.addons["cycles"].preferences
cp.compute_device_type = "METAL"
cp.refresh_devices()
cp.metalrt = "AUTO"
for d in cp.devices:
    if d.type == "METAL":
        d.use = True
sc.cycles.device = "GPU"
sc.cycles.samples = 8
sc.cycles.use_denoising = False
sc.render.resolution_x = 64
sc.render.resolution_y = 64
sc.render.filepath = "{out}"
bpy.ops.render.render(write_still=True)
print("WARM OK", "{out}")
"""


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="logo-maker-warmup-") as tmp:
        out = Path(tmp) / "logo-maker-warmup.png"
        script = Path(tmp) / "logo-maker-warmup.py"
        script.write_text(SCENE.format(out=out))
        started = time.monotonic()
        proc = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=600
        )
        elapsed = time.monotonic() - started
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-2000:]
            raise SystemExit(f"warmup render failed after {elapsed:.0f}s: {tail}")
        print(f"warmup render took {elapsed:.0f}s -> {out}")


if __name__ == "__main__":
    main()
