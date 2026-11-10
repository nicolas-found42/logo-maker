"""Isolated replay of the provenance-pinned OMP scene."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

from logo_maker.benchmark import verify_bundle


def replay_original(
    root: Path, output: Path, *, resolution: int = 2000, samples: int = 256, seed: int = 42
) -> dict:
    """Replay meaningful original construction with packaged assets on strict Metal.

    Historical CPU provenance remains in the manifest; this is a new GPU render.
    A 4000 px replay is downsampled through the production image operation.
    """
    import sys

    from logo_maker.blender import settings
    from logo_maker.blender.execution import render_verified
    from logo_maker.render import _downsample_final

    verified = verify_bundle(root)
    root, output = root.resolve(), output.resolve()
    if output.is_relative_to(root):
        raise ValueError("replay output must be outside the immutable fixture bundle")
    if output.exists():
        raise ValueError("replay output already exists; choose a fresh directory")
    output.mkdir(parents=True)
    started = time.monotonic()
    source = (root / "recipe/wax3d.py.txt").read_text()
    body = source[: source.index("sc = bpy.context.scene\nsc.render.engine")]
    for name in ("legend.json", "relief.json", "OpenSans-Bold-static.ttf"):
        # These are literal historical source paths, never temporary output destinations.
        body = body.replace(f"/tmp/logo/{name}", str(root / "recipe" / name))  # noqa: S108
    argv = sys.argv
    try:
        sys.argv = [
            "wax3d.py",
            "--",
            str(output / "unused.png"),
            "28",
            str(root / "recipe/poly_haven_studio_1k.hdr"),
            "gold",
            "cycles",
        ]
        exec(compile(body, "packaged-omp-wax3d.py", "exec"), {"__name__": "__main__"})  # noqa: S102
    finally:
        sys.argv = argv
    import bpy

    settings.apply_quality({"resolution": resolution, "samples": samples})
    bpy.context.scene.cycles.seed = seed
    bpy.context.scene.cycles.use_animated_seed = False
    setup_seconds = time.monotonic() - started
    report = render_verified(
        output / "replay.png",
        output / "execution.json",
        inputs={"fixture_manifest": root / "manifest.json"},
    )
    _downsample_final(output / "replay.png")
    report.update(
        {
            "fixture_manifest_sha256": verified["manifest_sha256"],
            "scene_setup_seconds": setup_seconds,
            "replay_kind": "new GPU reference replay",
            "total_seconds": time.monotonic() - started,
            "delivered_png_sha256": hashlib.sha256(
                (output / "replay.png").read_bytes()
            ).hexdigest(),
            "owner_review": "pending",
            "qualification": "incomplete",
        }
    )
    (output / "replay.json").write_text(json.dumps(report, indent=2) + "\n")
    shutil.copyfile(root / "manifest.json", output / "input-manifest.json")
    return report
