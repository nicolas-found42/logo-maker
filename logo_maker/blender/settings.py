"""Cycles device and sampling setup. The GPU block below is the configuration
measured fastest on Apple Silicon in assignments/research/logo-gpu-render.md —
Metal with `refresh_devices()` before `device = "GPU"`, MetalRT AUTO, OIDN on
GPU (which defaults off in 5.2.3 and must be set explicitly).
"""

from __future__ import annotations


def apply_cycles_gpu() -> None:
    """Enable Metal GPU rendering with the verified settings (order matters)."""
    import _cycles
    import bpy

    # --- device setup (order matters) ---
    cp = bpy.context.preferences.addons["cycles"].preferences
    cp.compute_device_type = "METAL"
    cp.refresh_devices()  # GPU device appears with use=True
    cp.metalrt = "AUTO"  # hardware ray tracing when beneficial
    available = {d[2] for d in _cycles.available_devices("METAL") if d[1] == "METAL"}
    selected = next((d for d in cp.devices if d.type == "METAL" and d.id in available), None)
    for d in cp.devices:
        d.use = d == selected
    if (
        len(available) != 1
        or selected is None
        or not selected.use
        or any(d.use and d.type != "METAL" for d in cp.devices)
    ):
        raise RuntimeError(
            "GPU-only policy: no enabled exclusive Metal GPU; CPU fallback forbidden"
        )

    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU"
    # Also override inherited command-line/session device masks in the native session.
    _cycles.set_device_override("METAL")


def apply_quality(quality: dict) -> None:
    """Sampling, denoising, and resolution for a compiled quality block."""
    import bpy

    sc = bpy.context.scene
    sc.cycles.use_adaptive_sampling = bool(quality.get("adaptive", False))
    sc.cycles.adaptive_threshold = float(quality.get("adaptive_threshold", 0.01))
    sc.cycles.samples = int(quality.get("samples", 256))
    sc.cycles.adaptive_min_samples = int(quality.get("min_samples", 0))
    sc.cycles.seed = int(quality.get("seed", 0))
    sc.cycles.use_animated_seed = False
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    sc.cycles.denoising_use_gpu = True  # default False in 5.2.3 — MUST set, else CPU OIDN
    sc.cycles.tile_size = 2048
    sc.cycles.use_auto_tile = True

    resolution = int(quality.get("resolution", 1000))
    sc.render.resolution_x = resolution
    sc.render.resolution_y = resolution
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
