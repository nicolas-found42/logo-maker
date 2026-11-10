"""Regression render: the bundled example concept must keep looking the same (SSIM >= 0.90 at 256 px)."""

from __future__ import annotations

import shutil
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


def test_unverified_alternate_renderer_is_operational_error(tmp_path: Path) -> None:
    """An alternate engine cannot borrow the builder's Cycles GPU attestation."""
    from logo_maker import pipeline, render
    from logo_maker.proc import ToolError

    concept = tmp_path / "concept"
    shutil.copytree(
        EXAMPLE / "concept",
        concept,
        ignore=shutil.ignore_patterns("*.png", "*.blend", "*.glb", ".build", "meshes"),
    )
    scene = concept / "scene.toml"
    scene.write_text(scene.read_text().replace('renderer = "cycles"', 'renderer = "luxcore"'))
    pipeline.prepare_motif(concept)
    with pytest.raises(ToolError, match="GPU-only policy"):
        render.render(concept, "test")
