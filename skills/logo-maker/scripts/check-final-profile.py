"""Check a scene's final sampling profile without starting a render."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("concept", type=Path, help="folder containing scene.toml")
    args = parser.parse_args()
    checkout = Path.cwd()
    if not (checkout / "logo_maker" / "render.py").is_file():
        parser.error("run from the logo-maker tool checkout using its Python environment")
    sys.path.insert(0, str(checkout))

    from logo_maker import host, render, scene
    from logo_maker.proc import ToolError
    from logo_maker.sampling import Budget

    concept = args.concept.resolve()
    try:
        recipe = scene.load_scene(concept / "scene.toml")
        if recipe["render"]["renderer"] != "cycles":
            parser.error("production profile preflight requires Cycles")
        budget = Budget(wall_seconds=120)
        quality = scene.sampling_quality(recipe, "final")
        runtime = render.machine_context(budget)
        package = checkout / "logo_maker"
        profile_controls = {"max_samples", "min_samples", "seed", "adaptive_threshold", "adaptive"}
        context = {
            **runtime,
            "stage": "final",
            "resolution": quality["resolution"],
            "settings_key": render.content_key(
                {
                    key: value
                    for key, value in recipe["render"].items()
                    if key not in profile_controls
                }
            ),
            "code_sha256": {
                str(path.relative_to(package)): render.sha256(path)
                for path in render.source_files(concept)
                if path.is_relative_to(package)
            },
            "material_presets": sorted({spec["preset"] for spec in recipe["materials"].values()}),
        }
        if any(component["kind"] == "bpy" for component in recipe["components"]):
            context["custom_scene_sha256"] = "unknown"
        result = host.run(
            {
                "operation": "sampling_controls",
                "concept_dir": str(concept),
                "config": recipe["sampling"],
                "context": context,
                "quality": quality,
            },
            budget,
            [],
        )
        state, reason = result["profile"]
        if state == "profile_stale":
            profile = concept / recipe["sampling"]["profile"]
            expected = json.loads(profile.read_text())["context"]
            actual = {
                key: value
                for key, value in context.items()
                if key not in {"material_presets", "custom_scene_sha256"}
            }
            mismatches = [
                key
                for key in sorted(expected.keys() | actual.keys())
                if expected.get(key) != actual.get(key)
            ]
            reason += ": " + ", ".join(mismatches)
    except (OSError, ValueError, KeyError, TypeError, ToolError, RuntimeError) as error:
        parser.exit(2, f"Profile preflight failed: {error}\n")
    print(f"{state}: {reason}")
    return 0 if state == "qualified" else 3


if __name__ == "__main__":
    sys.exit(main())
