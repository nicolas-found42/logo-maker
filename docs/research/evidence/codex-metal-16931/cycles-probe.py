"""Render a small real Cycles/OIDN scene in the chosen sandbox."""

from pathlib import Path

from logo_maker.blender.execution import render_verified
from logo_maker.blender.metal import require_metal_device
from logo_maker.blender.settings import apply_cycles_gpu, apply_quality

require_metal_device()

output = Path(__file__).resolve().parent
import bpy  # noqa: E402,F401 -- import only after native Metal visibility is proven

apply_cycles_gpu()
apply_quality({"resolution": 64, "samples": 4})
result = render_verified(output / "cycles-preflight.png", output / "cycles-preflight.json")
if (
    result["status"] != "verified"
    or result["denoiser_effective"]["device_type"] != "Metal"
    or [d["type"] for d in result["devices"] if d["use"]] != ["METAL"]
):
    raise SystemExit(f"GPU preflight did not verify: {result}")
print("Verified Cycles Metal and OIDN Metal")
