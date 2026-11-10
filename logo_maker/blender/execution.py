"""Fail-closed Metal tracing and independently observed OIDN execution.

OIDN_VERBOSE=2 reports the *created* device and executed filters in pinned bpy 5.2.3.
Missing/changed diagnostics are operational errors, never implicit CPU permission.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import re
import sys
import time
from pathlib import Path


def verify_denoiser_log(log: str) -> dict:
    """Require actual OIDN Metal device initialization and filter execution."""
    blocks = log.split("Intel(R) Open Image Denoise ")[1:]
    if not blocks:
        raise RuntimeError("GPU-only denoising unverified: missing OIDN runtime diagnostics")
    for block in blocks:
        types = re.findall(r"^\s*Type\s*:\s*(\S+)", block, re.MULTILINE)
        if types != ["Metal"] or "Filter: RT" not in block or "Image size:" not in block:
            raise RuntimeError("GPU-only denoising unverified or CPU fallback: refusing output")
    return {
        "device_type": "Metal",
        "oidn_version": blocks[0].splitlines()[0].strip(),
        "evidence": "OIDN_VERBOSE=2 created device and executed RT filters",
    }


def render_verified(
    png: Path,
    evidence: Path,
    *,
    inputs: dict[str, Path] | None = None,
    diagnostic_bytes: int = 0,
) -> dict:
    """Render to quarantine; publish only after runtime GPU verification.

    Call after authoring/quality changes. Reassert policy immediately before rendering.
    Native stdout/stderr is retained in a per-render log, including on failure.
    """
    import bpy

    from logo_maker.blender.settings import apply_cycles_gpu

    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.unlink(missing_ok=True)
    log_path = evidence.with_suffix(".log")
    pending = evidence.with_suffix(".unverified.png")
    pending.unlink(missing_ok=True)
    os.environ["OIDN_VERBOSE"] = "2"
    report = {"schema": 1, "policy": "metal-gpu-only", "status": "unverified"}
    original_filepath = (
        bpy.context.scene.render.filepath if hasattr(bpy.context.scene.render, "filepath") else ""
    )
    try:
        report["inputs_sha256"] = {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in (inputs or {}).items()
        }
        apply_cycles_gpu()
        cp = bpy.context.preferences.addons["cycles"].preferences
        sc = bpy.context.scene
        if not cp.has_oidn_gpu_devices():
            raise RuntimeError("GPU-only denoising unsupported on the selected Metal GPU")
        if not (
            sc.cycles.use_denoising
            and sc.cycles.denoiser == "OPENIMAGEDENOISE"
            and sc.cycles.denoising_use_gpu
        ):
            raise RuntimeError("GPU-only denoising required: OIDN GPU must be enabled")
        sc.render.filepath = str(pending.resolve())
        devices = [
            {"name": d.name, "id": d.id, "type": d.type, "use": bool(d.use)} for d in cp.devices
        ]
        report.update(
            {
                "schema": 1,
                "policy": "metal-gpu-only",
                "status": "unverified",
                "blender": bpy.app.version_string,
                "build": bpy.app.build_hash.decode(),
                "os": platform.platform(),
                "machine": platform.machine(),
                "devices": devices,
                "device_override": "METAL",
                "metalrt": cp.metalrt,
                "sampling": {
                    key: getattr(sc.cycles, key)
                    for key in (
                        "samples",
                        "use_adaptive_sampling",
                        "adaptive_threshold",
                        "adaptive_min_samples",
                        "seed",
                        "use_animated_seed",
                    )
                },
                "resolution": [sc.render.resolution_x, sc.render.resolution_y],
                "resolution_percentage": sc.render.resolution_percentage,
                "denoiser_requested": {
                    "name": sc.cycles.denoiser,
                    "gpu": sc.cycles.denoising_use_gpu,
                    "input_passes": sc.cycles.denoising_input_passes,
                },
                "timing_scope": "render, denoise and PNG write; excludes prior scene setup and verification",
                "kernel_cache_state": "unknown",
                "log": log_path.name,
            }
        )
        diagnostic = None
        if diagnostic_bytes:
            diagnostic = _enable_diagnostics(diagnostic_bytes)
        started = time.monotonic()
        cpu_started = time.process_time()
        # Flush Python and native buffers before redirecting/restoring process descriptors.
        libc = ctypes.CDLL(None)
        sys.stdout.flush()
        sys.stderr.flush()
        libc.fflush(None)
        saved = [os.dup(1), os.dup(2)]
        try:
            with log_path.open("wb") as stream:
                os.dup2(stream.fileno(), 1)
                os.dup2(stream.fileno(), 2)
                try:
                    bpy.ops.render.render(write_still=True)
                finally:
                    sys.stdout.flush()
                    sys.stderr.flush()
                    libc.fflush(None)
        finally:
            for fd, original in zip((1, 2), saved, strict=True):
                os.dup2(original, fd)
                os.close(original)
        report["seconds"] = time.monotonic() - started
        report["process_cpu_seconds"] = time.process_time() - cpu_started
        report["log_sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
        log = log_path.read_text(errors="replace")
        report["denoiser_effective"] = verify_denoiser_log(log)
        if diagnostic is not None:
            report["diagnostics"] = _save_diagnostics(
                evidence.with_suffix(".exr"), diagnostic_bytes, diagnostic
            )
        report["png_sha256"] = hashlib.sha256(pending.read_bytes()).hexdigest()
        pending.replace(png)
        report["status"] = "verified"
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        bpy.context.scene.render.filepath = original_filepath
        evidence.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _enable_diagnostics(max_bytes: int) -> dict:
    import bpy

    sc = bpy.context.scene
    layer = bpy.context.view_layer
    # A normal single-layer Combined + noisy/guides/count has <=24 float channels.
    # Custom AOVs, other enabled passes and multiple layers need a separate bound.
    extra = [
        p.identifier
        for p in layer.bl_rna.properties
        if p.identifier.startswith("use_pass_")
        and p.identifier not in {"use_pass_combined", "use_pass_cryptomatte_accurate"}
        and getattr(layer, p.identifier, False)
    ]
    pixels = (
        sc.render.resolution_x
        * sc.render.resolution_y
        * (sc.render.resolution_percentage / 100) ** 2
    )
    if (
        len(sc.view_layers) != 1
        or len(layer.aovs)
        or extra
        or pixels * 24 * 4 + 1048576 > max_bytes
    ):
        return {"status": "unknown", "reason": "diagnostic storage bound or custom pass scope"}
    try:
        layer.cycles.pass_debug_sample_count = True
        layer.cycles.denoising_store_passes = True
    except AttributeError:
        return {"status": "unknown", "reason": "bpy lacks sample/noisy passes"}
    return {"status": "enabled", "decoded_byte_bound": int(pixels * 24 * 4 + 1048576)}


def _save_diagnostics(path: Path, max_bytes: int, capability: dict) -> dict:
    import bpy

    if capability["status"] != "enabled":
        return capability
    image = bpy.context.scene.render.image_settings
    previous = (image.media_type, image.file_format, image.color_depth, image.exr_codec)
    started = time.monotonic()
    try:
        image.media_type = "MULTI_LAYER_IMAGE"
        image.file_format = "OPEN_EXR_MULTILAYER"
        image.color_depth = "32"
        image.exr_codec = "ZIP"
        bpy.data.images["Render Result"].save_render(str(path))
        if path.stat().st_size > max_bytes:
            path.unlink()
            return {"status": "unknown", "reason": "EXR exceeded diagnostic storage budget"}
        return {
            "status": "retained",
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "seconds": time.monotonic() - started,
            "scope": "lossless 32-bit multilayer EXR write and hash, after render",
        }
    except (RuntimeError, OSError, TypeError) as exc:
        path.unlink(missing_ok=True)
        return {"status": "unknown", "reason": str(exc)}
    finally:
        image.media_type, image.file_format, image.color_depth, image.exr_codec = previous
