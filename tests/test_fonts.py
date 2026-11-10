"""Offline tests for font spec parsing and static-file selection (no network)."""

import pytest

from logo_maker.fonts import FontSpec, FontSpecError, _pick_file, available_on_disk, parse_spec

STATIC = [
    {"name": "Example", "style": "normal", "weight": "400", "filename": "Example-Regular.ttf"}
]
VARIABLE = [
    {"name": "Example", "style": "normal", "weight": "400", "filename": "Example[wght].ttf"},
    {"name": "Example", "style": "italic", "weight": "400", "filename": "Example-Italic[wght].ttf"},
]


def test_parse_bare_family():
    assert parse_spec("Fraunces") == FontSpec("Fraunces", {})


def test_parse_axes():
    assert parse_spec("Fraunces:opsz=144,wght=600").axes == {"opsz": 144.0, "wght": 600.0}


def test_parse_italic_flag():
    assert parse_spec("Inter:ital=1").axes == {"ital": 1.0}


def test_str_round_trip():
    assert str(parse_spec("Fraunces:opsz=144,wght=700")) == "Fraunces:opsz=144,wght=700"


@pytest.mark.parametrize(
    "bad",
    ["", ":wght=700", "Fam:wght", "Fam:wght=bold", "Fam:toolong=1", "Fam:wght=1,opsz", "Fam:=1"],
)
def test_parse_errors(bad):
    with pytest.raises(FontSpecError):
        parse_spec(bad)


def test_pick_italic_file():
    assert (
        _pick_file(VARIABLE, parse_spec("Example:ital=1"))["filename"] == "Example-Italic[wght].ttf"
    )


def test_pick_variable_over_static():
    assert _pick_file(VARIABLE, parse_spec("Example:wght=700"))["filename"] == "Example[wght].ttf"


def test_axes_on_static_font_raise():
    with pytest.raises(FontSpecError):
        _pick_file(STATIC, parse_spec("Example:wght=700"))


def test_static_without_axes_ok():
    assert _pick_file(STATIC, parse_spec("Example"))["filename"] == "Example-Regular.ttf"


def test_available_on_disk_miss_is_none(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGO_MAKER_CACHE", str(tmp_path))
    assert available_on_disk("No Such Family XYZ") is None


def test_available_on_disk_bad_spec_is_none():
    assert available_on_disk("Bad:spec=:") is None
