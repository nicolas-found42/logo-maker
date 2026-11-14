"""Palette math: extraction, normalization, WCAG contrast and gates."""

import pytest
from PIL import Image as _PILImage

from logo_maker.palette import contrast, extract_colors, normalize, wcag_problems


def test_normalize_spellings():
    assert normalize("#abc") == "#AABBCC"
    assert normalize("abc") == "#AABBCC"
    assert normalize("#a1b2c3") == "#A1B2C3"
    assert normalize("  #FF0000 ") == "#FF0000"


def test_normalize_rejects():
    for bad in ("#ab", "#gggggg", "red", "", "#12345", "##000000", "#\ufb000000", "#00000\n"):
        with pytest.raises(ValueError, match="not a hex color"):
            normalize(bad)


def test_contrast_known_values():
    assert contrast("#1E4A7A", "#FFFFFF") == pytest.approx(9.07, abs=0.05)
    assert contrast("#1E4A7A", "#F8F6F1") == pytest.approx(8.40, abs=0.05)


def test_contrast_is_symmetric_and_bounded():
    assert contrast("#C96F2B", "#20242A") == pytest.approx(contrast("#20242A", "#C96F2B"))
    assert 1.0 <= contrast("#C96F2B", "#20242A") <= 21.0


def test_wcag_problems_boundaries():
    assert wcag_problems({"background": "#FFFFFF", "ink": "#000000"}) == []
    # #777777 on white is ~4.48:1, just under the 4.5 text floor.
    problems = wcag_problems({"background": "#FFFFFF", "ink": "#777777"})
    assert len(problems) == 1
    assert "ink on background" in problems[0]
    # Accent floor is 3.0: a too-pale accent fails, a mid gray passes.
    assert wcag_problems({"background": "#FFFFFF", "accent": "#BBBBBB"}) != []
    assert wcag_problems({"background": "#FFFFFF", "accent": "#777777"}) == []


def test_wcag_problems_skips_missing_roles():
    assert wcag_problems({"background": "#FFFFFF", "accent": "#BBBBBB"}) != []
    assert wcag_problems({"background": "#FFFFFF"}) == []
    assert "background" in wcag_problems({"ink": "#000000"})[0]


def test_extract_colors_solid(tmp_path):
    path = tmp_path / "red.png"
    _PILImage.new("RGBA", (40, 40), (255, 0, 0, 255)).save(path)
    assert extract_colors(path) == [("#FF0000", pytest.approx(1.0))]


def test_extract_colors_ignores_transparent(tmp_path):
    img = _PILImage.new("RGBA", (10, 2), (0, 0, 0, 0))
    for x in range(5):
        img.putpixel((x, 0), (0, 0, 255, 255))
        img.putpixel((x, 1), (0, 0, 255, 255))
    path = tmp_path / "half.png"
    img.save(path)
    colors = extract_colors(path, n=4)
    assert colors[0][0] == "#0000FF"
    assert colors[0][1] == pytest.approx(1.0)


def test_extract_colors_empty(tmp_path):
    path = tmp_path / "clear.png"
    _PILImage.new("RGBA", (8, 8), (0, 0, 0, 0)).save(path)
    assert extract_colors(path) == []
