"""Export set contract: exact sizes, ICO entries, a truthful manifest, and refusal of broken heroes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from logo_maker.export import AVATAR_SIZE, FAVICON_SIZES, HERO_SIZE, ExportError, export_all

PALETTE = {"primary": "#1E4A7A", "background": "#F8F6F1", "ink": "#16232E"}
MOTIF = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000">
<path d="M500 80 L880 820 L120 820 Z" fill="#1E4A7A"/>
</svg>
"""


def _concept(tmp_path: Path, draw) -> tuple[Path, Path]:
    concept = tmp_path / "concept"
    concept.mkdir()
    image = Image.new("RGBA", (1200, 900), (0, 0, 0, 0))
    draw(ImageDraw.Draw(image))
    image.save(concept / "final.png")
    motif = concept / "motif.svg"
    motif.write_text(MOTIF)
    return concept, motif


def _disc(d: ImageDraw.ImageDraw) -> None:
    d.ellipse((350, 200, 850, 700), fill=(30, 74, 122, 255))


def test_export_set_sizes_and_manifest(tmp_path: Path) -> None:
    concept, motif = _concept(tmp_path, _disc)
    out = tmp_path / "exports"
    manifest = export_all(concept, out, name="Sample Brand", palette=PALETTE, motif_svg=motif)

    hero = np.asarray(Image.open(manifest["hero-transparent"]).convert("RGBA"))
    assert hero.shape[:2] == (HERO_SIZE, HERO_SIZE)
    assert hero[0, 0, 3] == 0
    assert hero[HERO_SIZE // 2, HERO_SIZE // 2, 3] == 255

    for size in FAVICON_SIZES:
        assert Image.open(manifest[f"favicon-{size}"]).size == (size, size)
    ico = Image.open(manifest["favicon-ico"])
    assert {(16, 16), (32, 32), (48, 48)} <= set(ico.info["sizes"])

    avatar = Image.open(manifest["avatar-1024"]).convert("RGB")
    assert avatar.size == (AVATAR_SIZE, AVATAR_SIZE)
    paper = tuple(int(PALETTE["background"][i : i + 2], 16) for i in (1, 3, 5))
    px = np.asarray(avatar)
    assert tuple(px[0, 0]) == paper  # corners stay clear for circular crops
    assert tuple(px[AVATAR_SIZE // 2, AVATAR_SIZE // 2]) != paper

    for key in ("hero-paper", "mark-color", "mark-mono", "pwa-manifest", "contact-sheet"):
        assert manifest[key].is_file(), key
    assert "#1E4A7A" not in manifest["mark-mono"].read_text().upper()

    record = json.loads((out / "manifest.json").read_text())
    assert record["name"] == "Sample Brand"
    assert set(record["files"]) == set(manifest)
    for key, entry in record["files"].items():
        path = out / entry["path"]
        data = path.read_bytes()
        assert entry["bytes"] == len(data), key
        assert entry["sha256"] == hashlib.sha256(data).hexdigest(), key


@pytest.mark.parametrize(
    ("draw", "message"),
    [
        (lambda d: None, "fully transparent"),
        (lambda d: d.ellipse((-200, 200, 500, 900), fill=(30, 74, 122, 255)), "touches the frame"),
    ],
)
def test_broken_hero_refuses_to_export(tmp_path: Path, draw, message: str) -> None:
    concept, motif = _concept(tmp_path, draw)
    with pytest.raises(ExportError, match=message):
        export_all(concept, tmp_path / "exports", name="Sample", palette=PALETTE, motif_svg=motif)


def test_export_deadline_keeps_prior_exports(tmp_path):
    from logo_maker.sampling import Budget, SamplingLimit

    concept, motif = _concept(tmp_path, _disc)
    out = tmp_path / "exports"
    out.mkdir()
    (out / "prior.txt").write_text("last approved export")
    clock = [0.0]
    budget = Budget(wall_seconds=1, clock=lambda: clock[0])
    clock[0] = 2
    with pytest.raises(SamplingLimit, match="time_limit"):
        export_all(concept, out, name="Sample", palette=PALETTE, motif_svg=motif, budget=budget)
    assert (out / "prior.txt").read_text() == "last approved export"
