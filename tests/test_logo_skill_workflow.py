"""Exercise the runnable flat recipes with real motif tools and no provider credentials."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from PIL import IcoImagePlugin, Image

from logo_maker import motif

ROOT = Path(__file__).resolve().parents[1]
FLAT_GUIDE = ROOT / "skills/logo-maker/references/flat-assets.md"


def run_recipe(heading: str, *args: Path | int) -> None:
    section = FLAT_GUIDE.read_text().split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
    recipe = re.search(r"<<'PY'\n(.*?)\nPY\n", section, re.DOTALL)
    assert recipe is not None
    env = os.environ.copy()
    for key in ("OPENROUTER_API_KEY", "TYPESAFE_API_KEY"):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-", *map(str, args)],
        input=recipe.group(1),
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_flat_favicon_recipe_builds_from_motif_and_reuses_an_svg(tmp_path):
    concept = tmp_path / "Bicycle library"
    concept.mkdir()
    script = concept / "motif.py"
    script.write_text(
        "from logo_maker.motif import Motif\n"
        "m = Motif()\n"
        "ring = m.difference(m.circle(500, 500, 380), m.circle(500, 500, 220))\n"
        "m.add('wheel', ring, fill='#164A41')\n"
        "m.save('.')\n"
    )

    run_recipe("Build and check", concept)

    svg = concept / "motif.svg"
    assert motif.validate(svg) == []
    assert (concept / "motif-sizes.png").is_file()
    for size in (16, 32, 48, 180, 512):
        with Image.open(concept / f"favicon-{size}.png") as image:
            assert image.size == (size, size)
            assert image.getchannel("A").getpixel((size // 2, size // 2)) == 0
            assert image.getbbox() is not None
    with IcoImagePlugin.IcoImageFile(concept / "favicon.ico") as image:
        assert image.ico.sizes() == {(16, 16), (32, 32), (48, 48)}

    original = svg.read_bytes()
    script.unlink()
    run_recipe("Build and check", concept)
    assert svg.read_bytes() == original


def test_exact_svg_resize_pads_a_wide_wordmark_and_preserves_original(tmp_path):
    original = tmp_path / "Original brand mark.svg"
    artwork = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
        '<g transform="translate(25 0)">'
        '<rect width="150" height="100" fill="#164A41"/></g></svg>'
    )
    original.write_text(artwork)
    output = tmp_path / "handoff" / "avatar.png"

    run_recipe("Resize an original SVG without rewriting it", original, output, 64)

    assert original.read_text() == artwork
    with Image.open(output) as image:
        assert image.size == (64, 64)
        assert image.getbbox() == (8, 16, 56, 48)
        assert image.getpixel((32, 32)) == (22, 74, 65, 255)
