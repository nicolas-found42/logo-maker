"""Verify the immutable public subset; full tool/build/request snapshots remain in local jobs."""

from __future__ import annotations

import json

from logo_maker.blender.execution import verify_denoiser_log
from logo_maker.paths import REPO_ROOT
from logo_maker.refinement import digest


def verify_execution(folder):
    execution = json.loads((folder / "execution.json").read_text())
    if execution["status"] != "verified" or execution["device_override"] != "METAL":
        raise ValueError(f"unverified device: {folder}")
    selected = [d for d in execution["devices"] if d["use"]]
    if len(selected) != 1 or selected[0]["type"] != "METAL":
        raise ValueError(f"nonexclusive Metal selection: {folder}")
    if digest(folder / "execution.log") != execution["log_sha256"]:
        raise ValueError(f"changed runtime log: {folder}")
    verify_denoiser_log((folder / "execution.log").read_text())


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
            verify_execution(folder)
            revisions += 1
    print(
        f"Verified {revisions} revisions, {sources} authored-source files, exclusive Metal tracing and runtime OIDN Metal logs"
    )
    final = root / "evidence/final-runtime"
    if final.exists():
        verify_execution(final)
        sampling = json.loads((final / "sampling.json").read_text())
        if digest(final / "render.png") != sampling["delivered_sha256"]:
            raise ValueError("changed delivered final image")
        if digest(final / "execution.json") != sampling["execution_sha256"]:
            raise ValueError("changed final execution record")
        requests = list((final / "requests").glob("*.json"))
        measurement = json.loads((final / "measurement.json").read_text())
        if len(requests) != measurement["request_count"]:
            raise ValueError("final provider request count mismatch")
        assets = 0
        for path in requests:
            request = json.loads(path.read_text())
            if request["assets_status"] != "ready" or not request["answers"]:
                raise ValueError(f"incomplete final provider evidence: {path}")
            for asset in request["assets"].values():
                image = final / "assets" / f"{asset['sha256']}.{asset['format']}"
                if digest(image) != asset["sha256"]:
                    raise ValueError(f"changed provider asset: {image}")
                assets += 1
        print(
            f"Verified separate final GPU runtime and {len(requests)} provider requests/{assets} assets"
        )


if __name__ == "__main__":
    main()
