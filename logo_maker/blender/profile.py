"""Actual bpy environment fingerprint. No render and no CPU tracing permission."""

from __future__ import annotations

import json
import platform
import subprocess
from importlib.metadata import distribution, version
from pathlib import Path

from logo_maker.blender.metal import binary_archive_override, require_metal_device
from logo_maker.sampling_diagnostics import sha256


def environment() -> dict:
    require_metal_device()

    import bpy

    from logo_maker.blender.settings import apply_cycles_gpu

    apply_cycles_gpu()  # reuse #4, including clearing inherited CPU selections
    cp = bpy.context.preferences.addons["cycles"].preferences
    if not cp.has_oidn_gpu_devices():
        raise RuntimeError("GPU-only denoising unsupported; profile calibration forbidden")
    dist = distribution("bpy")
    libraries = {
        str(p): sha256(Path(str(dist.locate_file(p))))
        for p in dist.files or []
        if str(p).endswith(".dylib") and "OpenImageDenoise" in str(p)
    }
    hardware = {}
    for key in ("hw.model", "hw.memsize", "hw.ncpu", "machdep.cpu.brand_string", "kern.osversion"):
        proc = subprocess.run(["sysctl", "-n", key], capture_output=True, text=True, check=False)
        hardware[key] = proc.stdout.strip() if proc.returncode == 0 else "unknown"
    lockfile = Path(__file__).resolve().parents[2] / "uv.lock"
    return {
        "python": platform.python_version(),
        "render_stack": {
            name: version(name)
            for name in (
                "OpenImageIO",
                "Pillow",
                "numpy",
                "trimesh",
                "manifold3d",
                "fonttools",
                "skia-pathops",
                "build123d",
                "sdf",
                "pymeshlab",
            )
        },
        "lockfile_sha256": sha256(lockfile) if lockfile.is_file() else None,
        "blender": bpy.app.version_string,
        "build": bpy.app.build_hash.decode(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "hardware": hardware,
        "oidn_libraries_sha256": libraries,
        "oidn_version": "runtime log required",
        "backend": "METAL",
        **binary_archive_override(),
        "metalrt": cp.metalrt,
        "devices": [{"name": d.name, "id": d.id, "type": d.type} for d in cp.devices if d.use],
        "denoiser": "OPENIMAGEDENOISE",
        "denoising_input_passes": "RGB_ALBEDO_NORMAL",
    }


if __name__ == "__main__":
    print(json.dumps(environment(), sort_keys=True))
