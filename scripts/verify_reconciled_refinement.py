"""Verify retained reconciliation evidence without making an artistic approval claim."""

from __future__ import annotations

import json

from verify_refinement_evidence import verify_execution

from logo_maker.paths import REPO_ROOT
from logo_maker.refinement import digest


def verify(root) -> None:
    manifest = json.loads((root / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        if digest(root / name) != expected:
            raise ValueError(f"changed evidence: {name}")
    sources = 0
    for case in manifest["cases"]:
        folder = root / case["folder"]
        record = json.loads((folder / "revision.json").read_text())
        if digest(folder / "render.png") != record["image_sha256"]:
            raise ValueError(f"changed rendered image: {case['concept']}")
        if set(case["sources"]) != set(record["source_sha256"]):
            raise ValueError(f"incomplete source inventory: {case['concept']}")
        for name, source in case["sources"].items():
            if digest(root / source) != record["source_sha256"][name]:
                raise ValueError(f"changed authored/tool source: {name}")
            sources += 1
        verify_execution(folder)
    for retained in manifest.get("requests", []):
        request = json.loads((root / retained["path"]).read_text())
        if request["assets_status"] != "ready" or not request["answers"]:
            raise ValueError(f"incomplete provider request: {retained['path']}")
        if set(retained["assets"]) != set(request["assets"]):
            raise ValueError(f"incomplete provider assets: {retained['path']}")
        for ref, path in retained["assets"].items():
            if digest(root / path) != request["assets"][ref]["sha256"]:
                raise ValueError(f"changed provider image: {path}")
    runtime = root / manifest.get("final_runtime", "snapshots/final-runtime")
    verify_execution(runtime)
    sampling = json.loads((runtime / "sampling.json").read_text())
    if digest(runtime / "render.png") != sampling["delivered_sha256"]:
        raise ValueError("changed delivered final image")
    requests = list((runtime / "requests").glob("*.json"))
    for path in requests:
        request = json.loads(path.read_text())
        if request["assets_status"] != "ready" or not request["answers"]:
            raise ValueError(f"incomplete provider request: {path.name}")
        for asset in request["assets"].values():
            path = runtime / "assets" / f"{asset['sha256']}.{asset['format']}"
            if digest(path) != asset["sha256"]:
                raise ValueError(f"changed provider image: {path.name}")
    print(
        f"Verified {len(manifest['cases'])} rendered cases, {sources} source bindings, "
        f"{len(manifest['files'])} retained files, Metal/OIDN evidence and {len(requests)} final QA request(s)."
    )
    print("Artistic qualification remains authoring_needed; no production approval is inferred.")


def main() -> None:
    for bundle in (
        "reconciliation",
        "review-followup",
        "artwork-probe-20261111",
        "paper-exposure-20261111",
        "current-concept-20261111",
        "deadline-persistence-20261111",
        "deadline-concurrency-20261111",
    ):
        print(f"Checking {bundle}")
        verify(REPO_ROOT / "benchmarks/refinement" / bundle)


if __name__ == "__main__":
    main()
