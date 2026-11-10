"""Cycles device and sampling setup. The GPU block below is the configuration
measured fastest on Apple Silicon in assignments/research/logo-gpu-render.md —
Metal with `refresh_devices()` before `device = "GPU"`, MetalRT AUTO, OIDN on
GPU (which defaults off in 5.2.3 and must be set explicitly).
"""

from __future__ import annotations


def apply_cycles_gpu() -> None:
    """Enable Metal GPU rendering with the verified settings (order matters)."""
    import bpy

    # --- device setup (order matters) ---
    cp = bpy.context.preferences.addons["cycles"].preferences
    cp.compute_device_type = "METAL"
    cp.refresh_devices()  # GPU device appears with use=True
    cp.metalrt = "AUTO"  # hardware ray tracing when beneficial
    for d in cp.devices:
        if d.type == "METAL":
            d.use = True

    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU"


def apply_quality(quality: dict) -> None:
    """Sampling, denoising, and resolution for a compiled quality block."""
    import bpy

    sc = bpy.context.scene
    sc.cycles.use_adaptive_sampling = bool(quality.get("adaptive", False))
    sc.cycles.adaptive_threshold = float(quality.get("adaptive_threshold", 0.01))
    sc.cycles.samples = int(quality.get("samples", 256))
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
