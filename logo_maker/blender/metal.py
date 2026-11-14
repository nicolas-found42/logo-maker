"""Check GPU visibility without importing Blender or opening a scene."""

from __future__ import annotations

import ctypes
import os
import platform


def require_metal_device() -> None:
    """Fail before bpy starts on hosts and sandboxes that expose no Metal device."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("Metal rendering requires Apple Silicon macOS")

    metal = ctypes.CDLL("/System/Library/Frameworks/Metal.framework/Metal")
    default_device = metal.MTLCreateSystemDefaultDevice
    default_device.argtypes = ()
    default_device.restype = ctypes.c_void_p
    if not default_device():
        raise RuntimeError(
            "The current process has no Metal GPU device. "
            "Stop the 3D operation and check GPU access in its execution environment."
        )


def binary_archive_override() -> dict[str, str]:
    """Bind an explicit Cycles Metal shader archive override to runtime provenance."""
    setting = "CYCLES_METAL_DISABLE_BINARY_ARCHIVES"
    if (value := os.environ.get(setting)) is not None:
        return {setting: value}
    return {}
