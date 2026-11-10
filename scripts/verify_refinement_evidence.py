"""Verify the immutable public subset; full tool/build/request snapshots remain in local jobs."""

from __future__ import annotations

import json

from logo_maker.blender.execution import verify_denoiser_log
from logo_maker.paths import REPO_ROOT
from logo_maker.refinement import digest


def main() -> None:
    root = REPO_ROOT / "benchmarks" / "refinement"
    summary = json.loads((root / "evidence" / "summary.json").read_text())
    revisions = sources = 0
    for case in summary["cases"].values():
        for revision in case["revisions"]:
            folder = root / revision["evidence"]
            if digest(folder / "render.png") != revision["image_sha256"]:
                raise ValueError(f"changed image: {folder}")
            record = json.loads((folder / "revision.json").read_text())
            for name, expected in record["source_sha256"].items():
                if name.startswith("concept/"):
                    source = folder / "sources" / name
                    if digest(source) != expected:
                        raise ValueError(f"changed source: {source}")
                    sources += 1
            execution = json.loads((folder / "execution.json").read_text())
            if execution["status"] != "verified" or execution["device_override"] != "METAL":
                raise ValueError(f"unverified device: {folder}")
            selected = [d for d in execution["devices"] if d["use"]]
            if len(selected) != 1 or selected[0]["type"] != "METAL":
                raise ValueError(f"nonexclusive Metal selection: {folder}")
            if digest(folder / "execution.log") != execution["log_sha256"]:
                raise ValueError(f"changed runtime log: {folder}")
            verify_denoiser_log((folder / "execution.log").read_text())
            revisions += 1
    print(
        f"Verified {revisions} revisions, {sources} authored-source files, exclusive Metal tracing and runtime OIDN Metal logs"
    )


if __name__ == "__main__":
    main()
