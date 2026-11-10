"""Offline QA tests for logo_maker.checks (veil, margin, color, edge)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from logo_maker.checks import (
    ALIASED_FRACTION,
    OBJECT_ALPHA,
    VEIL_HAZE_FRACTION,
    alpha_report,
    color_report,
    edge_report,
    margin_report,
)


def _disc(
    path: Path, size: int = 200, radius: int = 60, color: tuple[int, int, int] = (200, 60, 40)
) -> Path:
    """Hard-edged disc on a transparent background (PIL shapes are not AA)."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    c = size // 2
    draw.ellipse([c - radius, c - radius, c + radius, c + radius], fill=(*color, 255))
    im.save(path)
    return path


def _veil(path: Path, size: int = 200) -> Path:
    """Object over a faint 2%-alpha rectangle covering most of the frame."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 5))
    draw = ImageDraw.Draw(im)
    c = size // 2
    draw.ellipse([c - 50, c - 50, c + 50, c + 50], fill=(40, 120, 200, 255))
    im.save(path)
    return path


def test_clean_disc_has_no_veil(tmp_path: Path) -> None:
    png = _disc(tmp_path / "clean.png")
    report = alpha_report(png)
    assert report["veil"] is False
    assert report["haze_fraction"] == 0.0
    assert report["min_bg_alpha"] == 0
    assert report["bbox"] == [40, 40, 161, 161]


def test_faint_rectangle_reads_as_veil(tmp_path: Path) -> None:
    png = _veil(tmp_path / "veil.png")
    report = alpha_report(png)
    assert report["veil"] is True
    assert report["haze_fraction"] > VEIL_HAZE_FRACTION


def test_empty_image_has_no_body(tmp_path: Path) -> None:
    png = tmp_path / "empty.png"
    Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(png)
    assert alpha_report(png)["bbox"] is None
    assert margin_report(png)["empty"] is True


def test_margin_cut_off_boundary(tmp_path: Path) -> None:
    size = 200
    # Occupied rows 8..191: margins 0.04 exactly -> not cut off.
    alpha = np.zeros((size, size), dtype=np.uint8)
    alpha[8:192, 8:192] = 255
    Image.fromarray(np.dstack([alpha] * 3 + [alpha]).astype(np.uint8), "RGBA").save(
        tmp_path / "edge-ok.png"
    )
    assert margin_report(tmp_path / "edge-ok.png", min_margin=0.04)["cut_off"] is False
    alpha2 = np.zeros((size, size), dtype=np.uint8)
    alpha2[7:193, 7:193] = 255
    Image.fromarray(np.dstack([alpha2] * 3 + [alpha2]).astype(np.uint8), "RGBA").save(
        tmp_path / "edge-cut.png"
    )
    cut = margin_report(tmp_path / "edge-cut.png", min_margin=0.04)
    assert cut["cut_off"] is True
    assert cut["margins"]["left"] == pytest.approx(0.035)


def test_touching_frame_reports_touching(tmp_path: Path) -> None:
    alpha = np.zeros((64, 64), dtype=np.uint8)
    alpha[:, :] = 255
    Image.fromarray(np.dstack([alpha] * 3 + [alpha]).astype(np.uint8), "RGBA").save(
        tmp_path / "full.png"
    )
    report = margin_report(tmp_path / "full.png")
    assert report["touching"] is True
    assert report["cut_off"] is True


def test_color_report_finds_palette_role(tmp_path: Path) -> None:
    png = _disc(tmp_path / "red.png", color=(200, 60, 40))
    report = color_report(png, {"primary": "#C83C28", "ink": "#111111"})
    assert report["empty"] is False
    assert "primary" in report["roles_present"]
    assert "ink" not in report["roles_present"]


def test_color_report_empty_when_transparent(tmp_path: Path) -> None:
    png = tmp_path / "empty.png"
    Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(png)
    assert color_report(png, {"primary": "#C83C28"})["empty"] is True


def test_hard_edge_reads_aliased(tmp_path: Path) -> None:
    png = _disc(tmp_path / "hard.png")
    report = edge_report(png)
    assert report["edge_pixels"] == 0  # no graded pixels on a binary edge
    assert report["aliasing"] > ALIASED_FRACTION
    assert report["aliased"] is True


def test_graded_edge_reads_clean(tmp_path: Path) -> None:
    from logo_maker.imageops import downsample

    big = _disc(tmp_path / "big.png", size=400, radius=120)
    small = tmp_path / "small.png"
    downsample(big, small, 100)  # lanczos grades the edge
    report = edge_report(small)
    assert report["smooth_steps"] > 0
    assert report["aliased"] is False


def test_object_alpha_constant_used(tmp_path: Path) -> None:
    assert OBJECT_ALPHA == 8
