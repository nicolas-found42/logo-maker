"""Offline tests for generative 2D tools (local binaries and node scripts only)."""

import shutil
import tempfile
from pathlib import Path

import pytest

from logo_maker import twod_tools as T
from logo_maker.motif import HEX_RE, MotifError, flatten_d, parse_d, poly_area

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")


def _needs(*names: str):
    for name in names:
        path = Path("js/node_modules") / name / "package.json"
        if not (Path(__file__).resolve().parents[1] / path).exists():
            pytest.skip(f"js dependency {name} not installed")
    return True


def _valid(shapes: list[T.Shape]) -> list[T.Shape]:
    assert shapes
    for shape in shapes:
        assert HEX_RE.match(shape.fill), shape.fill
        assert parse_d(shape.d)
    return shapes


def test_sketchy_returns_fill_and_outline():
    _needs("roughjs")
    shapes = _valid(T.sketchy("M200 200 L800 200 L500 800 Z", seed=7))
    assert len(shapes) == 2


def test_freehand_outline_is_closed():
    _needs("perfect-freehand")
    (shape,) = _valid(T.freehand([(100, 100), (300, 250, 0.9), (500, 100, 0.4)], size=20))
    assert shape.d.rstrip().endswith("Z")


def test_voronoi_cell_count_matches_points():
    _needs("d3-delaunay")
    pts = [(100, 100), (400, 200), (250, 500), (600, 600), (700, 150)]
    assert len(_valid(T.voronoi(pts))) == len(pts)


def test_delaunay_triangulates():
    _needs("d3-delaunay")
    assert len(_valid(T.delaunay([(100, 100), (400, 200), (250, 500), (600, 600)]))) == 2


def test_low_poly_triangles_have_hex_fills():
    _needs("trianglify")
    shapes = _valid(T.low_poly(300, 200, cell_size=60, seed=3))
    assert len(shapes) > 10


def test_voxels_box_produces_faces():
    _needs("heerich")
    assert len(_valid(T.voxels({"cells": [[0, 0, 0], [1, 0, 0], [0, 1, 1]]}))) > 0


def test_plotter_lines_merges_and_outlines():
    pytest.importorskip("vpype")
    (shape,) = _valid(T.plotter_lines(["M100 500 L400 500", "M400 500 L700 500"], width=6))
    area = sum(poly_area(c) for c in flatten_d(shape.d))
    assert area == pytest.approx(600 * 6, rel=0.05)


def test_primitive_abstract_shapes():
    if shutil.which("primitive") is None and not Path.home().joinpath("go/bin/primitive").exists():
        pytest.skip("primitive not installed")
    from PIL import Image, ImageDraw

    tmp = Path(tempfile.mkdtemp()) / "ref.png"
    canvas = Image.new("RGB", (128, 128), (240, 240, 235))
    ImageDraw.Draw(canvas).ellipse([20, 20, 108, 108], fill=(30, 60, 120))
    canvas.save(tmp)
    shapes = _valid(T.primitive_abstract(tmp, shapes=6, mode=1))
    assert len(shapes) >= 6


def test_fontforge_glyphs_ligature():
    if shutil.which("fontforge") is None:
        pytest.skip("fontforge not installed")
    system = "/System/Library/Fonts/Helvetica.ttc"
    if not Path(system).exists():
        pytest.skip("no system font to build from")
    shapes = _valid(
        T.fontforge_glyphs(
            system,
            [
                {"new": "uniE000"},
                {"add": {"from": "A", "into": "uniE000", "dx": 0, "dy": 0}},
                {"add": {"from": "V", "into": "uniE000", "dx": 700, "dy": 0}},
            ],
        )
    )
    assert len(shapes) == 1


def test_trace_geometry_and_style_guard(tmp_path):
    pytest.importorskip("vtracer")
    from PIL import Image, ImageDraw

    from logo_maker import trace as tr

    img = tmp_path / "ref.png"
    canvas = Image.new("RGB", (64, 64), (255, 255, 255))
    ImageDraw.Draw(canvas).rectangle([16, 16, 48, 48], fill=(200, 30, 30))
    canvas.save(img)
    svg = tr.trace(img, colors=3)
    assert "transform" not in svg
    assert tr.shapes(svg)
    with pytest.raises(tr.TraceError):
        tr.trace(img, mode="style")
    with pytest.raises(MotifError):
        parse_d("m0 0 l10 10")


@pytest.mark.parametrize("cell_size", [0, -4, float("nan"), True])
def test_low_poly_rejects_unusable_cell_size(cell_size):
    with pytest.raises(MotifError, match="cell_size"):
        T.low_poly(100, 100, cell_size=cell_size)


def test_low_poly_bounds_the_point_count():
    with pytest.raises(MotifError, match="raise cell_size"):
        T.low_poly(100_000, 100_000, cell_size=1)


def test_voxels_spec_must_be_a_mapping():
    with pytest.raises(MotifError, match="must be a mapping"):
        T.voxels("cells")  # ty: ignore[invalid-argument-type]


def test_primitive_path_ignores_an_empty_gopath(monkeypatch, tmp_path):
    import subprocess

    monkeypatch.chdir(tmp_path)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "primitive").write_text("#!/bin/sh\n")
    (tmp_path / "bin" / "primitive").chmod(0o755)
    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="\n", stderr=""),
    )
    assert T.primitive_path() is None


@pytest.mark.parametrize(
    ("ops", "match"),
    [
        ([5], "want one of"),
        ([{"add": {"into": "a"}}], "from = None"),
        ([{"add": {"from": "a", "into": "b", "dx": "x"}}], "dx = 'x'"),
        ([{"advance": {"glyph": "a", "width": float("nan")}}], "width = nan"),
    ],
)
def test_fontforge_ops_are_validated_before_fontforge_runs(ops, match):
    with pytest.raises(MotifError, match=match):
        T._fontforge_script("font.ttf", ops)
