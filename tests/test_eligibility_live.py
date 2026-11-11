"""Owner-labeled calibration controls. Run explicitly with -m live and a configured key."""

import json
from dataclasses import replace

import pytest

from logo_maker.brief import Brief, Reference, load
from logo_maker.eligibility import compare_visual
from logo_maker.jev.client import JevClient
from logo_maker.paths import REPO_ROOT, LogoDir


@pytest.mark.live
@pytest.mark.parametrize(
    ("asset", "appearance"),
    [
        (
            "original-seal-2000.png",
            "Blue wax seal, evenly shaded gold C/check and legend, restrained reflections; green ribbons.",
        ),
        (
            "reconstruction-rendered-2000.png",
            "Blue wax seal, highly reflective gold C/check and legend, glossy rounded highlights; green ribbons.",
        ),
    ],
)
def test_approved_craft_self_controls(tmp_path, asset, appearance):
    image = REPO_ROOT / "benchmarks/omp/assets" / asset
    brief = Brief(
        "Chief of Staff",
        "A meeting assistant",
        ("clear",),
        intended_appearance=appearance,
        references=(Reference(image, "craft", appearance),),
    )
    result = compare_visual(
        brief,
        {"metaphor": "A C whose opening holds a check"},
        image,
        JevClient(LogoDir(tmp_path)),
        label="approved-self-control",
    )
    # Owner approved craft, not every fit/technical dimension or a preference ranking.
    assert [r["status"] for r in result["craft"]] == ["pass", "pass"]


@pytest.mark.live
def test_rejected_skill_swap_does_not_advance(tmp_path):
    source = REPO_ROOT / "benchmarks/omp/qualification/skill-swap"
    reference = REPO_ROOT / "benchmarks/omp/assets/original-seal-2000.png"
    brief = replace(
        load(source / "brief.toml"),
        intended_appearance="Layered matte forest-green and sage paper, crisp cut edges and controlled folds.",
        references=(
            Reference(
                reference,
                "craft",
                "Blue wax seal with restrained reflections and evenly shaded gold details.",
            ),
        ),
    )
    concept = json.loads((source / "gather.json").read_text())
    result = compare_visual(
        brief,
        {"metaphor": concept["metaphor_text"], "treatment": concept["treatment_text"]},
        REPO_ROOT / "benchmarks/omp/assets/gather-hero.png",
        JevClient(LogoDir(tmp_path)),
        label="rejected-skill-swap",
    )
    assert result["status"] != "pass"
