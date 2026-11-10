"""Provenance verification and isolated replay of the OMP reference fixture.

This module never selects brand defaults or awards aesthetic quality from fidelity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DIMENSIONS = {"fidelity", "craftsmanship", "brief_fit", "preference"}


def verify_bundle(root: Path) -> dict:
    """Verify every retained dependency before allowing replay; never mutate fixtures."""
    root = root.resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest["schema"] != 1:
        raise ValueError("unsupported benchmark schema")
    paths = set()
    for asset in manifest["assets"]:
        path = (root / asset["path"]).resolve()
        if not path.is_relative_to(root) or Path(asset["path"]).is_absolute():
            raise ValueError("benchmark asset must stay inside bundle")
        if asset["path"] in paths:
            raise ValueError("duplicate benchmark asset")
        paths.add(asset["path"])
        if not asset["origin"] or not asset["permitted_use"]:
            raise ValueError("asset provenance and permitted use are required")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]:
            raise ValueError(f"missing asset or hash mismatch: {asset['path']}")
    for case in manifest["cases"]:
        if case["asset"] not in paths or set(case["owner_labels"]) != DIMENSIONS:
            raise ValueError("case requires a pinned asset and four independent owner dimensions")
    return {
        "assets_verified": len(paths),
        "cases": manifest["cases"],
        "qualification": "incomplete",
        "remaining_gaps": manifest["remaining_gaps"],
        "manifest_sha256": hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "replay"))
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resolution", type=int, choices=(2000, 4000), default=2000)
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.action == "verify":
        report = verify_bundle(args.bundle)
    else:
        from logo_maker.blender.replay import replay_original

        if args.output is None or args.samples < 1:
            parser.error("replay requires --output and positive --samples")
        report = replay_original(
            args.bundle,
            args.output,
            resolution=args.resolution,
            samples=args.samples,
            seed=args.seed,
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
