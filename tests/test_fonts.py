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


def test_italic_picks_the_italic_file_of_a_static_family():
    files = [*STATIC, {**STATIC[0], "style": "italic", "filename": "Example-Italic.ttf"}]
    assert _pick_file(files, parse_spec("Example:ital=1"))["filename"] == "Example-Italic.ttf"
    with pytest.raises(FontSpecError):
        _pick_file(files, parse_spec("Example:ital=1,wght=700"))


def test_interrupted_download_leaves_no_cached_file(tmp_path, monkeypatch):
    import httpx

    from logo_maker import fonts
    from logo_maker.proc import ToolError

    class Reset:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def iter_bytes(self):
            yield b"partial"
            raise httpx.ReadError("connection reset")

    monkeypatch.setattr(fonts.httpx, "stream", lambda *a, **k: Reset())
    dest = tmp_path / "raw" / "Example.ttf"
    with pytest.raises(ToolError, match="could not download"):
        fonts._get("https://example.invalid/Example.ttf", dest)
    assert list(dest.parent.iterdir()) == []


def test_damaged_cached_font_is_removed_and_named(tmp_path, monkeypatch):
    from logo_maker import fonts
    from logo_maker.proc import ToolError

    monkeypatch.setenv("LOGO_MAKER_CACHE", str(tmp_path))
    files = [{"name": "Example", "style": "normal", "weight": "400", "filename": "Example.ttf"}]
    monkeypatch.setattr(fonts, "_family_dirpath", lambda family: ("ofl", "example"))
    monkeypatch.setattr(fonts, "_metadata", lambda top, dirname: (files, [], "OFL-1.1"))
    raw = tmp_path / "fonts" / "raw" / "ofl" / "example" / "Example.ttf"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"partial-bytes")
    with pytest.raises(ToolError, match=r"was not a font.*run again"):
        fonts.resolve("Example")
    assert not raw.exists()  # the next run downloads it again


@pytest.mark.parametrize("text", ["[]", '{"roboto": []}', "{"])
def test_damaged_family_index_is_a_cache_miss(tmp_path, monkeypatch, text):
    from logo_maker import fonts

    monkeypatch.setenv("LOGO_MAKER_CACHE", str(tmp_path))
    (tmp_path / "fonts").mkdir()
    (tmp_path / "fonts" / "index.json").write_text(text)
    assert fonts._load_index() == {}
