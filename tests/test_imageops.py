"""Offline tests for logo_maker.imageops (sizes, modes, premultiplied correctness)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from logo_maker.imageops import composite_on, downsample, pad_square, soft_shadow


@pytest.fixture
def disc(tmp_path: Path) -> Path:
    path = tmp_path / "clean.png"
    im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([40, 40, 160, 160], fill=(200, 60, 40, 255))
    im.save(path)
    return path


def test_downsample_long_edge(tmp_path: Path) -> None:
    src = tmp_path / "wide.png"
    Image.new("RGBA", (300, 100), (10, 20, 30, 255)).save(src)
    dst = downsample(src, tmp_path / "out.png", 120)
    assert Image.open(dst).size == (120, 40)


def test_downsample_keeps_transparency_and_color(tmp_path: Path, disc: Path) -> None:
    dst = downsample(disc, tmp_path / "small.png", 64)
    arr = np.asarray(Image.open(dst))
    assert arr.shape == (64, 64, 4)
    # Corners stay transparent black: no halo bleed from premultiplied filtering.
    assert arr[0, 0, 3] == 0
    assert arr[0, 0, :3].max() == 0
    # Center keeps the mark color (no darkening from unassociated filtering).
    center = arr[32, 32]
    assert center[3] == 255
    assert center[0] > 150
    assert center[1] < 110


def test_pad_square_centers(tmp_path: Path) -> None:
    src = tmp_path / "wide.png"
    Image.new("RGBA", (300, 100), (1, 2, 3, 255)).save(src)
    dst = pad_square(src, tmp_path / "sq.png", 128)
    arr = np.asarray(Image.open(dst))
    assert arr.shape == (128, 128, 4)
    assert arr[0, 0, 3] == 0  # padding is transparent
    assert arr[64, 64, 3] == 255  # content is centered


def test_composite_on_flattens(tmp_path: Path, disc: Path) -> None:
    dst = composite_on(disc, "#F4F1EA", tmp_path / "flat.png")
    im = Image.open(dst)
    assert im.mode == "RGB"
    assert im.getpixel((0, 0)) == (244, 241, 234)
    assert im.getpixel((100, 100)) == (200, 60, 40)


def test_composite_on_default_dst(disc: Path) -> None:
    dst = composite_on(disc, "#FFFFFF")
    try:
        assert dst.name == "clean-flat.png"
        assert Image.open(dst).mode == "RGB"
    finally:
        dst.unlink(missing_ok=True)


def test_soft_shadow_shape_and_strength(tmp_path: Path, disc: Path) -> None:
    shadow = soft_shadow(disc, opacity=0.26, blur=28)
    assert shadow.size == (200, 200)
    assert shadow.mode == "RGBA"
    peak = np.asarray(shadow)[:, :, 3].max()
    assert 0 < peak <= round(255 * 0.26)
