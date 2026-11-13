"""Offline tests for motif geometry, the contract, and derived formats."""

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image as _PILImage

from logo_maker import motif as M

CIRCLE = M.Motif.circle(500, 500, 200)
SQUARE = M.Motif.rect(400, 400, 300, 300)


def _area(d: str) -> float:
    return sum(M.poly_area(c) for c in M.flatten_d(d))


def test_union_area_invariant():
    assert _area(M.union(CIRCLE, SQUARE)) == pytest.approx(
        _area(CIRCLE) + _area(SQUARE) - _area(M.intersection(CIRCLE, SQUARE)), rel=0.02
    )


def test_difference_area_invariant():
    assert _area(M.difference(CIRCLE, SQUARE)) == pytest.approx(
        _area(CIRCLE) - _area(M.intersection(CIRCLE, SQUARE)), rel=0.02
    )


def test_xor_area_invariant():
    assert _area(M.xor(CIRCLE, SQUARE)) == pytest.approx(
        _area(CIRCLE) + _area(SQUARE) - 2 * _area(M.intersection(CIRCLE, SQUARE)), rel=0.02
    )


def test_empty_operands():
    assert M.parse_d(M.union("", CIRCLE))
    assert M.union("", "") == ""
    assert M.difference("", CIRCLE) == ""
    assert M.intersection(CIRCLE, "") == ""
    assert M.parse_d(M.xor(SQUARE, ""))


def test_flatten_closes_contours_and_keeps_holes():
    outer = M.Motif.circle(500, 500, 200)
    donut = M.difference(outer, M.Motif.circle(500, 500, 100))
    contours = M.flatten_d(donut)
    assert len(contours) == 2
    for contour in contours:
        assert contour[0] == contour[-1]
    hole = _area(donut) - _area(outer)  # the hole contour adds area back under even-odd fill
    assert hole == pytest.approx(math.pi * 100 * 100, rel=0.03)


def test_flatten_curves_at_twelve_steps():
    contours = M.flatten_d("M0 0 C100 0 100 100 0 100")
    assert len(contours[0]) == 12 + 2  # one move + 12 samples, closed by repeating the start
    assert contours[0][0] == contours[0][-1]


def _svg(paths: str, viewbox: str = "0 0 1000 1000") -> Path:
    import tempfile

    svg = Path(tempfile.mkdtemp()) / "m.svg"
    svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}">{paths}</svg>')
    return svg


def _path(pid: str, d: str, extra: str = "") -> str:
    return f'<path id="{pid}" d="{d}" fill="#123456"{extra}/>'


def test_validate_clean():
    assert M.validate(_svg(_path("a", CIRCLE))) == []


def test_validate_catches_relative():
    (problems := M.validate(_svg('<path id="a" d="m0 0 l10 10" fill="#123456"/>')))
    assert problems
    assert "relative" in problems[0]


def test_validate_catches_transform_and_stroke():
    svg = _svg(
        _path("a", CIRCLE, ' transform="translate(1)"') + _path("b", SQUARE, ' stroke="black"')
    )
    problems = M.validate(svg)
    assert any("transform" in p for p in problems)
    assert any("stroke" in p for p in problems)


def test_validate_catches_duplicates_out_of_circle_and_viewbox():
    svg = _svg(
        _path("a", CIRCLE) + _path("a", SQUARE) + _path("big", M.Motif.circle(500, 500, 900)),
        viewbox="0 0 10 10",
    )
    problems = M.validate(svg)
    assert any("duplicate" in p for p in problems)
    assert any("leaves the radius" in p for p in problems)
    assert any("viewBox" in p for p in problems)


def test_validate_catches_non_path_and_bad_fill():
    svg = _svg(
        '<rect x="1" y="1" width="2" height="2"/>'
        + _path("a", CIRCLE, "").replace('fill="#123456"', 'fill="red"')
    )
    problems = M.validate(svg)
    assert any("<rect>" in p for p in problems)
    assert any("fill" in p for p in problems)


def test_transform_full_turn_is_identity():
    assert _area(M.transform_d(CIRCLE, rotate_deg=360)) == pytest.approx(_area(CIRCLE), rel=1e-6)


def test_fit_lands_inside_circle():
    fitted = M.fit("M0 0 L2000 0 L2000 500 L0 500 Z")
    x0, y0, x1, y1 = M.bbox_of_d(fitted)
    for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        assert math.hypot(px - M.CX, py - M.CY) <= M.RADIUS + M.GEOM_TOL


def test_stroke_area_matches_width_times_length():
    got = _area(M.stroke_d("M100 500 L900 500", 20, cap="butt"))
    assert got == pytest.approx(800 * 20, rel=0.02)


def test_parse_errors():
    for bad in ["", "M0 0 L", "M0 0 Q", "Z 10", "M0 0 X10 10", "m0 0"]:
        with pytest.raises(M.MotifError):
            M.parse_d(bad)


def test_save_validate_flatten_round_trip(tmp_path):
    m = M.Motif()
    m.add("disc", M.Motif.circle(500, 500, 300), fill="#123456", role="primary")
    m.add("hole", M.Motif.circle(500, 500, 100), fill="#ABCDEF", role="accent", height=0.5, layer=1)
    svg = m.save(tmp_path)
    assert M.validate(svg) == []
    data = M.flatten(svg)
    assert [layer["id"] for layer in data["layers"]] == ["disc", "hole"]
    assert all(c[0] == c[-1] for layer in data["layers"] for c in layer["contours"])


def test_rasterize_mono_silhouette_size_sheet(tmp_path):
    m = M.Motif()
    m.add("disc", M.Motif.circle(500, 500, 300), fill="#123456")
    svg = m.save(tmp_path)
    png = M.rasterize(svg, 64, tmp_path / "p.png")
    assert png.stat().st_size > 0
    mono = M.mono(svg, "#000000", tmp_path / "mono.svg")
    tree = ET.parse(mono).getroot()  # noqa: S314 - test reads a file it just wrote
    fills = {el.get("fill") for el in tree.iter() if el.tag.rsplit("}", 1)[-1] == "path"}
    assert fills == {"#000000"}
    sil = M.silhouette(M.flatten(svg))
    assert sil
    assert abs(sum(M.poly_area(c) for c in sil) - math.pi * 300**2) / (math.pi * 300**2) < 0.02
    sheet = M.size_sheet(svg, tmp_path / "sheet.png")
    assert sheet.stat().st_size > 0
    im = _PILImage.open(sheet).convert("RGB")
    present = {c for _, c in im.getcolors(maxcolors=1_000_000) or []}
    assert {(250, 250, 250), (205, 205, 205)} <= present  # checkerboard shows light and dark ink


def test_run_motif_script(tmp_path):
    concept = tmp_path / "concept"
    concept.mkdir()
    (concept / "motif.py").write_text(
        "from logo_maker.motif import Motif\nm = Motif()\n"
        "m.add('disc', Motif.circle(500, 500, 300), fill='#123456')\nm.save('.')\n"
    )
    assert M.run_motif_script(concept) == concept / "motif.svg"


def test_run_motif_script_failure(tmp_path):
    concept = tmp_path / "concept"
    concept.mkdir()
    (concept / "motif.py").write_text("raise RuntimeError('boom')\n")
    with pytest.raises(M.MotifError, match="boom"):
        M.run_motif_script(concept)


def test_run_motif_script_survives_output_that_is_not_utf8(tmp_path):
    concept = tmp_path / "concept"
    concept.mkdir()
    (concept / "motif.py").write_text(
        "import sys\nsys.stdout.buffer.write(b'\\xff')\nsys.stdout.flush()\n"
        "from logo_maker.motif import Motif\nm = Motif()\n"
        "m.add('disc', Motif.circle(500, 500, 300), fill='#123456')\nm.save('.')\n"
    )
    assert M.run_motif_script(concept) == concept / "motif.svg"
    (concept / "motif.py").write_text(
        "import sys\nsys.stderr.buffer.write(b'\\xff boom')\nsys.exit(1)\n"
    )
    with pytest.raises(M.MotifError, match="exited 1: \ufffd boom"):
        M.run_motif_script(concept)


def _disc_script(radius: int, then: str = "") -> str:
    return (
        "from logo_maker.motif import Motif\nm = Motif()\n"
        f"m.add('disc', Motif.circle(500, 500, {radius}), fill='#123456')\nm.save('.')\n{then}"
    )


@pytest.mark.parametrize(
    ("script", "match"),
    [
        ("print('forgot to save')\n", r"wrote no motif\.svg"),
        (_disc_script(100, "import sys\nsys.exit(7)\n"), "exited 7"),
        ("import os\nos.mkdir('motif.svg')\n", r"wrote no motif\.svg"),
    ],
)
def test_failed_rerun_keeps_the_previous_motif_and_none_of_its_own(tmp_path, script, match):
    concept = tmp_path / "concept"
    concept.mkdir()
    (concept / "motif.py").write_text(_disc_script(300))
    M.run_motif_script(concept)
    good = {name: (concept / name).read_bytes() for name in ("motif.svg", "motif.json")}
    (concept / "motif.py").write_text(script)
    with pytest.raises(M.MotifError, match=match):
        M.run_motif_script(concept)
    if (concept / "motif.svg").is_dir():  # the script's own directory stays; nothing is merged
        assert (concept / "motif.json").read_bytes() == good["motif.json"]
    else:
        assert {n: (concept / n).read_bytes() for n in good} == good


def test_failed_first_run_leaves_no_motif(tmp_path):
    concept = tmp_path / "concept"
    concept.mkdir()
    (concept / "motif.py").write_text(_disc_script(100, "import sys\nsys.exit(7)\n"))
    with pytest.raises(M.MotifError, match="exited 7"):
        M.run_motif_script(concept)
    assert not (concept / "motif.svg").exists()
    assert not (concept / "motif.json").exists()


def _system_font():
    for candidate in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def test_text_advance_matches_sum_of_advances(monkeypatch):
    from fontTools.ttLib import TTFont

    from logo_maker import fonts

    system = _system_font()
    if system is None:
        pytest.skip("no system font to measure against")
    real_ttfont = TTFont

    def fake(path, *args, **kwargs):
        if str(path).endswith(".ttc"):
            return real_ttfont(path, fontNumber=0)
        return real_ttfont(path)

    monkeypatch.setattr(fonts, "TTFont", fake)
    monkeypatch.setattr(fonts, "resolve", lambda spec, on_asset=None: Path(system))
    d, advance = fonts.text_path("AVo", "Example", 100, 0, 500)
    assert d
    assert advance == pytest.approx(sum(fonts.advances("AVo", "Example")) * 100)


@pytest.mark.parametrize("height", ["nan", "inf"])
def test_validate_rejects_non_finite_height(height):
    svg = _svg(_path("a", CIRCLE)).read_text().replace("<path", f'<path data-height="{height}"', 1)
    path = _svg("")
    path.write_text(svg)
    assert any("height" in problem for problem in M.validate(path))


def test_fit_scales_a_line_by_its_non_zero_axis():
    x0, y0, x1, y1 = M.bbox_of_d(M.fit("M100 500 L1900 500 Z"))
    assert y0 == pytest.approx(y1)
    assert x1 - x0 == pytest.approx(M.RADIUS * math.sqrt(2), abs=0.01)  # default box side


def test_flatten_names_a_layer_with_no_area(tmp_path):
    svg = _svg(_path("ghost", M.Motif.circle(500, 500, 0)))
    with pytest.raises(M.MotifError, match="'ghost' has no area"):
        M.flatten(svg, tmp_path / "m.json")


def test_text_path_empty_text_needs_no_font_and_uncovered_text_is_an_error(monkeypatch):
    from fontTools.ttLib import TTFont

    from logo_maker import fonts

    assert fonts.text_path("", "No Such Family XYZ", 100, 0, 0) == ("", 0.0)
    system = _system_font()
    if system is None:
        pytest.skip("no system font to cover")
    monkeypatch.setattr(fonts, "TTFont", lambda path, *a, **k: TTFont(path, fontNumber=0))
    monkeypatch.setattr(fonts, "resolve", lambda spec, on_asset=None: Path(system))
    with pytest.raises(fonts.FontSpecError, match="U\\+E000"):
        fonts.text_path("A\ue000", "Example", 100, 0, 0)


@pytest.mark.parametrize("d", ["M0 0 L1e999 1", "M0 0 L inf 1", "M nan nan L1 1"])
def test_path_data_must_be_finite(d):
    with pytest.raises(M.MotifError, match="not a finite number"):
        M.Motif.path(d)


@pytest.mark.parametrize("width", [0, -3, math.nan, math.inf])
def test_stroke_width_must_be_positive_and_finite(width):
    with pytest.raises(M.MotifError, match="stroke width"):
        M.stroke_d("M0 0 L100 0 L100 100", width)


@pytest.mark.parametrize(
    ("size", "x", "match"),
    [(0, 0, "above 0"), (-100, 0, "above 0"), (math.nan, 0, "finite"), (10, math.inf, "finite")],
)
def test_glyphs_rejects_unusable_size_and_position(size, x, match):
    with pytest.raises(M.MotifError, match=match):  # checked before any font is fetched
        M.Motif.glyphs("A", "Example", size, x, 500)
