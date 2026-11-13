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
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except OSError as exc:
        raise ValueError(f"cannot read {manifest_path}: {exc.strerror or exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{manifest_path} is not valid JSON ({exc.msg})") from exc
    except (UnicodeDecodeError, RecursionError) as exc:  # binary, or nested beyond the parser
        raise ValueError(f"{manifest_path} is not readable JSON ({exc})") from exc
    if not isinstance(manifest, dict) or type(manifest.get("schema")) is not int:
        raise ValueError("manifest must be an object with an integer schema")
    if manifest["schema"] != 1:
        raise ValueError("unsupported benchmark schema")
    for key in ("assets", "cases", "remaining_gaps"):
        if not isinstance(manifest.get(key), list):
            raise ValueError(f"manifest {key} must be a list")
    if not manifest["assets"]:
        raise ValueError("manifest pins no assets")
    fields = ("path", "origin", "permitted_use", "sha256")
    paths = set()
    for asset in manifest["assets"]:
        if not isinstance(asset, dict) or any(not isinstance(asset.get(f), str) for f in fields):
            raise ValueError(f"each asset needs string {', '.join(fields)}")
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
        labels = case.get("owner_labels") if isinstance(case, dict) else None
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("asset"), str)
            or case["asset"] not in paths
            or not isinstance(labels, (list, dict))
            or not all(isinstance(label, str) for label in labels)
            or set(labels) != DIMENSIONS
        ):
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
        try:
            report = verify_bundle(args.bundle)
        except ValueError as exc:
            parser.error(f"{args.bundle}: {exc}")
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
