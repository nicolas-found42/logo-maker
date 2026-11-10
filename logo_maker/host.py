"""CPU host work in a disposable, deadline-owned process; never a render backend."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(payload: dict) -> dict:
    operation = payload["operation"]
    if operation == "load_config":
        from logo_maker.scene import load_scene

        return {"sampling": load_scene(Path(payload["concept_dir"]) / "scene.toml")["sampling"]}
    if operation == "compile":
        from logo_maker import scene
        from logo_maker.render import dependency_hashes

        assets = []
        source = scene.compile(
            payload["concept_dir"],
            payload["quality"],
            lambda key, source, license, path: assets.append(
                {"key": key, "source": source, "license": license, "path": path}
            ),
        )
        data = json.loads(source.read_text())
        return {
            "scene_json": str(source),
            "scene": data,
            "dependencies": dependency_hashes(Path(payload["concept_dir"]), data),
            "assets": assets,
        }
    if operation == "process_image":
        from logo_maker.render import _alpha_cleanup_png, _downsample_final
        from logo_maker.sampling_diagnostics import analyze_exr, sha256

        png = Path(payload["png"])
        if payload["quality"] == "final":
            _downsample_final(png)
        if payload["alpha_cleanup"]:
            _alpha_cleanup_png(png)
        return {
            "diagnostics": analyze_exr(
                Path(payload["exr"]), cap=payload["cap"], max_bytes=payload["max_bytes"]
            ),
            "delivered_sha256": sha256(png),
        }
    if operation == "artifact_current":
        from logo_maker.render import _artifact_current_local

        folder = Path(payload["concept_dir"])
        current = _artifact_current_local(folder, payload["quality"])
        record = (
            json.loads((folder / ".build" / f"{payload['quality']}.sampling.json").read_text())
            if current
            else {}
        )
        return {"current": current, "context": record.get("context", {})}
    raise ValueError(f"unknown host operation {operation!r}")


if __name__ == "__main__":
    print(json.dumps(main(json.loads(sys.stdin.read()))), flush=True)
