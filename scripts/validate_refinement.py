#!/usr/bin/env python3
"""Prepare/replay retained creative fixtures; inspection remains a separate agent action.

Example: python scripts/validate_refinement.py paper v1 --out /tmp/refinement-paper
Then open the returned image, write the requested inspection, and use --resume.
Repeat with v2 in the same --out folder to test structural revision and comparison.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from logo_maker import pipeline
from logo_maker.paths import REPO_ROOT, LogoDir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", choices=["paper", "metal"])
    parser.add_argument("version", choices=["v1", "v2", "v3", "v4"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    fixture = REPO_ROOT / "benchmarks" / "refinement" / "fixtures" / f"{args.brief}-{args.version}"
    logo = LogoDir(args.out.resolve())
    cid = json.loads((fixture / "concept.json").read_text())["id"]
    if not args.resume:
        if not logo.brief.exists():
            pipeline.new(logo, args.brief)
        shutil.copy2(fixture / "brief.toml", logo.brief)
        (logo.ideation / "shortlist.json").write_text(json.dumps({"ids": [cid]}))
        folder = logo.concept(cid)
        for path in fixture.iterdir():
            if path.name != "brief.toml":
                shutil.copy2(path, folder / path.name)
    try:
        result = pipeline.refine(logo)
    except pipeline.AuthoringNeeded as exc:
        print(
            json.dumps(
                {"status": "authoring_needed", "message": str(exc), "details": exc.details},
                indent=2,
            )
        )
        return 3
    print(
        json.dumps(
            {
                "status": "done",
                "counts": {
                    k: v
                    for k, v in result.items()
                    if k not in {"revisions", "comparisons", "selection"}
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
