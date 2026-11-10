"""Strict execution policy at the Blender settings and runtime evidence boundaries."""

import sys
from types import SimpleNamespace as NS

import pytest

from logo_maker.blender import settings


def blender(monkeypatch, devices):
    prefs = NS(devices=devices, refresh_devices=lambda: None)
    scene = NS(render=NS(), cycles=NS())
    monkeypatch.setitem(
        sys.modules,
        "bpy",
        NS(context=NS(preferences=NS(addons={"cycles": NS(preferences=prefs)}), scene=scene)),
    )
    monkeypatch.setitem(
        sys.modules,
        "_cycles",
        NS(
            available_devices=lambda backend: [(d.name, d.type, d.id) for d in devices],
            set_device_override=lambda value: None,
        ),
    )
    return prefs, scene


def test_gpu_setup_clears_inherited_cpu_and_enables_disabled_metal(monkeypatch):
    cpu = NS(type="CPU", name="CPU", id="cpu", use=True)
    gpu = NS(type="METAL", name="Apple M5 Pro", id="metal", use=False)
    blender(monkeypatch, [cpu, gpu])
    settings.apply_cycles_gpu()
    assert not cpu.use
    assert gpu.use


def test_missing_metal_is_operational_error(monkeypatch):
    cpu = NS(type="CPU", name="CPU", id="cpu", use=True)
    blender(monkeypatch, [cpu])
    with pytest.raises(RuntimeError, match="Metal GPU"):
        settings.apply_cycles_gpu()
    assert not cpu.use


def test_denoiser_runtime_requires_executed_metal_filters():
    from logo_maker.blender.execution import verify_denoiser_log

    good = "Intel(R) Open Image Denoise 2.5.0\n  Device : Apple M5 Pro\n    Type : Metal\nFilter: RT\nImage size: 64x64\n"
    assert verify_denoiser_log(good)["device_type"] == "Metal"
    for log in (
        "",
        good.replace("Metal", "CPU"),
        good.split("Filter:")[0],
        good + "Intel(R) Open Image Denoise 2.5.0\nType : CPU\nFilter: RT\nImage size: 64x64\n",
    ):
        with pytest.raises(RuntimeError, match="denois"):
            verify_denoiser_log(log)


def test_stale_metal_preference_is_not_an_available_gpu(monkeypatch):
    cpu = NS(type="CPU", name="CPU", id="cpu", use=True)
    stale = NS(type="METAL", name="unplugged", id="gone", use=True)
    blender(monkeypatch, [cpu, stale])
    monkeypatch.setitem(
        sys.modules,
        "_cycles",
        NS(
            available_devices=lambda backend: (("CPU", "CPU", "cpu"),),
            set_device_override=lambda value: None,
        ),
    )
    with pytest.raises(RuntimeError, match="Metal GPU"):
        settings.apply_cycles_gpu()


def test_unsupported_denoising_records_failure_without_publishing(monkeypatch, tmp_path):
    import json

    from logo_maker.blender.execution import render_verified

    prefs, scene = blender(monkeypatch, [NS(type="METAL", name="GPU", id="metal", use=True)])
    prefs.has_oidn_gpu_devices = lambda: False
    scene.cycles = NS(use_denoising=True, denoiser="OPENIMAGEDENOISE", denoising_use_gpu=True)
    with pytest.raises(RuntimeError, match="denoising unsupported"):
        render_verified(tmp_path / "result.png", tmp_path / "execution.json")
    assert not (tmp_path / "result.png").exists()
    assert json.loads((tmp_path / "execution.json").read_text())["status"] == "unverified"


@pytest.mark.parametrize(
    "diagnostics",
    ["", "Intel(R) Open Image Denoise 2.5.0\nType: CPU\nFilter: RT\nImage size: 64x64\n"],
)
def test_unverified_runtime_does_not_publish_or_replace_prior_result(
    monkeypatch, tmp_path, diagnostics
):
    import os
    from pathlib import Path

    from logo_maker.blender.execution import render_verified

    prefs, scene = blender(monkeypatch, [NS(type="METAL", name="GPU", id="metal", use=True)])
    prefs.has_oidn_gpu_devices = lambda: True
    scene.render.image_settings = NS()
    scene.view_settings = NS()
    settings.apply_quality({"resolution": 64, "samples": 4})
    scene.cycles.adaptive_min_samples = 0
    scene.cycles.seed = 42
    scene.cycles.use_animated_seed = False
    scene.render.filepath = "previous.png"
    bpy = sys.modules["bpy"]
    monkeypatch.setattr(
        bpy, "app", NS(version_string="5.2.3", build_hash=b"e13b728c6880"), raising=False
    )

    def native_render(**kwargs):
        Path(scene.render.filepath).write_bytes(b"unverified new image")
        os.write(1, diagnostics.encode())

    monkeypatch.setattr(bpy, "ops", NS(render=NS(render=native_render)), raising=False)
    png = tmp_path / "result.png"
    png.write_bytes(b"usable prior result")
    with pytest.raises(RuntimeError, match="denois"):
        render_verified(png, tmp_path / "execution.json")
    assert png.read_bytes() == b"usable prior result"
    assert scene.render.filepath == "previous.png"
