"""Live calibration of #2's visual gates; historical images have no execution-policy verdict.

Usage: uv run --locked python scripts/validate_eligibility.py --output DIR
Sends retained artwork to the configured Jev provider. No secrets enter the evidence.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from logo_maker.brief import Brief, Reference, load
from logo_maker.eligibility import compare_visual, sha256
from logo_maker.jev.client import JevClient, JevError
from logo_maker.paths import REPO_ROOT, LogoDir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    logo = LogoDir(args.output)
    client = JevClient(logo)
    assets = REPO_ROOT / "benchmarks/omp/assets"
    original = assets / "original-seal-2000.png"
    reconstructed = assets / "reconstruction-rendered-2000.png"
    restrained = "A blue wax seal with evenly shaded gold lettering and C/check, restrained reflections and muted finish; green ribbons."
    glossy = "A blue wax seal with highly reflective gold lettering and C/check, strong highlights and rounded edges; folded green ribbon tips."
    chief_concept = {
        "metaphor": "A serif C whose opening holds a check stroke; Chief of Staff remembers the meeting, you make the call.",
        "treatment": "wax seal with ring legend and crossed ribbons",
    }
    cases = [
        (
            "chief-original-self",
            original,
            original,
            restrained,
            restrained,
            chief_concept,
            "approved",
        ),
        (
            "chief-reconstruction-self",
            reconstructed,
            reconstructed,
            glossy,
            glossy,
            chief_concept,
            "approved",
        ),
        (
            "chief-original-vs-glossy",
            original,
            reconstructed,
            restrained,
            glossy,
            chief_concept,
            "approved",
        ),
        (
            "chief-glossy-vs-original",
            reconstructed,
            original,
            glossy,
            restrained,
            chief_concept,
            "approved",
        ),
    ]
    source = REPO_ROOT / "benchmarks/omp/qualification/skill-swap"
    for name in ("fold", "gather", "commons"):
        authored = json.loads((source / f"{name}.json").read_text())
        concept = {
            "metaphor": authored["metaphor_text"],
            "treatment": authored["treatment_text"],
            "material": authored["material_text"],
        }
        cases.append(
            (
                f"skill-swap-{name}",
                assets / f"{name}-hero.png",
                original,
                "Layered matte paper in forest green and pale sage, soft restrained shadows, crisp cut edges.",
                restrained,
                concept,
                "overall-rejected; per-dimension owner labels unknown",
            )
        )
    rows = []
    for label, candidate, reference, intended, ref_intended, concept, owner in cases:
        brief = Brief(
            "Chief of Staff" if label.startswith("chief") else "Skill Swap",
            "A meeting assistant that remembers the meeting so you make the call."
            if label.startswith("chief")
            else "A community for discovering and sharing reusable agent skills.",
            ("deliberate", "clear"),
            intended_appearance=intended,
            references=(Reference(reference, "craft", ref_intended),),
        )
        if label.startswith("skill-swap"):
            brief = replace(
                load(source / "brief.toml"),
                intended_appearance=intended,
                references=brief.references,
            )
        row = {
            "case": label,
            "candidate_sha256": sha256(candidate),
            "reference_sha256": sha256(reference),
            "owner_feedback": owner,
            "intended_appearance": intended,
            "preference": "unranked",
            "execution_policy": "not assessed: historical visual calibration only",
        }
        try:
            flat = (
                (source / f"{label.removeprefix('skill-swap-')}.svg")
                if label.startswith("skill-swap-")
                else (
                    REPO_ROOT / "benchmarks/omp/recipe/reconstruction/motif.svg"
                    if candidate == reconstructed
                    else assets / "original-mark.svg"
                )
            )
            row["rubric_sha256"] = sha256(REPO_ROOT / "logo_maker/jev/questions.py")
            row.update(
                compare_visual(brief, concept, candidate, client, label=label, flat_mark=flat)
            )
        except JevError as exc:
            row.update(status="api_error", error=str(exc))
        rows.append(row)
        (args.output / "calibration.json").write_text(json.dumps(rows, indent=2) + "\n")
        print(label, row["status"], flush=True)


if __name__ == "__main__":
    main()
