"""Read sample counts from real multilayer EXR subimages, not frame averages."""

import numpy as np
import OpenImageIO as oiio

from logo_maker.sampling_diagnostics import analyze_exr


def test_normalized_sample_subimage_uses_cap_and_foreground_mask(tmp_path):
    path = tmp_path / "diagnostic.exr"
    combined = np.zeros((4, 4, 4), dtype=np.float32)
    combined[1:3, 1:3] = [0.02, 0.02, 0.02, 1]
    counts = np.zeros((4, 4, 1), dtype=np.float32)
    counts[1:3, 1:3, 0] = [[0.25, 0.5], [1, 1]]
    specs = [oiio.ImageSpec(4, 4, 4, oiio.FLOAT), oiio.ImageSpec(4, 4, 1, oiio.FLOAT)]
    specs[0].channelnames = [
        "ViewLayer.Combined.R",
        "ViewLayer.Combined.G",
        "ViewLayer.Combined.B",
        "ViewLayer.Combined.A",
    ]
    specs[1].channelnames = ["ViewLayer.Debug Sample Count.X"]
    out = oiio.ImageOutput.create(str(path))
    assert out is not None
    assert out.open(str(path), specs)
    assert out.write_image(combined)
    assert out.open(str(path), specs[1], "AppendSubimage")
    assert out.write_image(counts)
    out.close()
    report = analyze_exr(path, cap=256, max_bytes=1000000)
    assert report["status"] == "available"
    foreground = report["regions"]["foreground"]
    assert foreground["pixels"] == 4
    assert foreground["p50"] == 192
    assert foreground["near_cap_fraction"] == 0.5
    assert report["regions"]["dark"]["pixels"] == 4
    assert len(report["subimages"]) == 2


def test_missing_or_over_budget_diagnostics_are_unknown(tmp_path):
    missing = tmp_path / "missing.exr"
    assert analyze_exr(missing, cap=4096, max_bytes=100)["status"] == "unknown"
