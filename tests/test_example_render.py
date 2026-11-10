"""Regression render: the bundled example concept must keep looking the same (SSIM >= 0.90 at 256 px)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from skimage.metrics import structural_similarity

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "chief-of-staff"
MIN_SSIM = 0.90


def _rgba_on_white(path: Path) -> np.ndarray:
    image = Image.open(path).convert("RGBA")
    canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
    canvas.alpha_composite(image)
    return np.asarray(canvas.convert("RGB"), dtype=np.float64) / 255.0


@pytest.mark.render
def test_example_concept_matches_reference(tmp_path: Path) -> None:
    from logo_maker import pipeline, render

    concept = tmp_path / "concept"
    shutil.copytree(
        EXAMPLE / "concept",
        concept,
        ignore=shutil.ignore_patterns("*.png", "*.blend", "*.glb", ".build", "meshes"),
    )
    pipeline.prepare_motif(concept)
    result = render.render(concept, "test")

    reference = _rgba_on_white(EXAMPLE / "reference-256.png")
    rendered = _rgba_on_white(result.png)
    assert rendered.shape == reference.shape
    score = structural_similarity(reference, rendered, channel_axis=2, data_range=1.0)
    assert score >= MIN_SSIM, (
        f"SSIM {score:.3f} < {MIN_SSIM}; compare {result.png} with the reference"
    )


@pytest.mark.render
def test_example_concept_renders_with_luxcore(tmp_path: Path) -> None:
    """The scene export path plus LuxCore halts at its sample count and leaves a transparent background."""
    concept = tmp_path / "concept"
    shutil.copytree(
        EXAMPLE / "concept",
        concept,
        ignore=shutil.ignore_patterns("*.png", "*.blend", "*.glb", ".build", "meshes"),
    )
    scene = concept / "scene.toml"
    scene.write_text(scene.read_text().replace('renderer = "cycles"', 'renderer = "luxcore"'))
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "from logo_maker import pipeline, render\n"
        "pipeline.prepare_motif(Path(sys.argv[1]))\n"
        "print(render.render(Path(sys.argv[1]), 'test').png)\n"
    )
    # A subprocess with a deadline: a LuxCore session that never halts blocks inside C++,
    # so only killing the process turns that regression into a failure instead of a hung run.
    done = subprocess.run(
        [sys.executable, "-c", script, str(concept)],
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    image = Image.open(done.stdout.strip().splitlines()[-1])
    assert image.mode == "RGBA"
    assert image.size == (256, 256)
    assert image.getchannel("A").getextrema() == (0, 255)
