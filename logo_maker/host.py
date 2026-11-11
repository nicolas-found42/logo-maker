"""CPU host work in a disposable, deadline-owned process; never a render backend."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from logo_maker import owned_process
from logo_maker.proc import ToolError
from logo_maker.sampling import Budget


def run(payload: dict, budget: Budget, stages: list[dict]) -> dict:
    started = time.monotonic()
    status = "failed"
    try:
        proc = owned_process.run(
            [sys.executable, "-m", "logo_maker.host"],
            input_text=json.dumps(payload),
            budget=budget,
            label=payload["operation"],
        )
        if proc.returncode:
            raise ToolError(
                f"host {payload['operation']} failed: {(proc.stderr or proc.stdout)[-2000:]}"
            )
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        status = "completed"
        return result
    finally:
        stages.append(
            {
                "operation": payload["operation"],
                "status": status,
                "seconds": time.monotonic() - started,
                "execution": "owned_cpu_worker",
                "timing_scope": "startup, CPU host work, output transfer and cleanup",
            }
        )


def main(payload: dict) -> dict:
    operation = payload["operation"]
    if operation == "write_json":
        from logo_maker.publication import _record

        _record(Path(payload["path"]), payload["data"])
        return {}
    if operation == "read_json":
        import hashlib

        path = Path(payload["path"])
        if not path.exists():
            return {"data": payload.get("default"), "sha256": None}
        raw = path.read_bytes()
        return {"data": json.loads(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if operation == "append_jsonl":
        path = Path(payload["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as handle:
            handle.write(json.dumps(payload["data"]) + "\n")
        return {}
    if operation == "runlog_load":
        from logo_maker.runlog import RunLog

        return {"data": RunLog(Path(payload["path"])).data}
    if operation == "pipeline_inputs":
        from dataclasses import asdict

        from logo_maker import brief, pipeline
        from logo_maker.paths import LogoDir

        logo = LogoDir(Path(payload["root"]))
        data = asdict(brief.load(logo.brief))
        for reference in data["references"]:
            reference["path"] = str(reference["path"])
        result = {"brief": data}
        if payload.get("brand"):
            result["brand"] = asdict(pipeline.brand(logo))
        if payload.get("finalists"):
            result["finalists"] = json.loads((logo.ideation / "finalists.json").read_text())["ids"]
        if payload.get("winner"):
            result["winner"] = pipeline.winner(logo)
        return result
    if operation == "apply_fixes":
        from logo_maker.pipeline import _apply_fixes

        return {"changes": _apply_fixes(Path(payload["path"]), set(payload["failures"]))}
    if operation == "remove_path":
        from logo_maker.publication import _remove

        _remove(Path(payload["path"]))
        return {}
    if operation in {"publish", "recover_publication", "clean_publication"}:
        from logo_maker import publication

        if operation == "publish":
            return publication.apply(payload)
        if operation == "recover_publication":
            return publication.recover(Path(payload["journal"]), Path(payload["lock"]))
        return publication.clean(Path(payload["journal"]))
    if operation == "render_setup":
        (Path(payload["concept_dir"]) / ".build").mkdir(exist_ok=True)
        return {}
    if operation == "render_attempt":
        folder = Path(payload["directory"])
        folder.mkdir()
        (folder / "scene.json").write_text(json.dumps(payload["scene"], indent=2))
        return {}
    if operation == "render_execution":
        import hashlib

        path = Path(payload["path"])
        raw = path.read_bytes()
        return {"record": json.loads(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if operation == "render_record":
        import shutil
        import uuid

        from logo_maker.publication import _record

        path = Path(payload["path"])
        if path.exists():
            if json.loads(path.read_text()).get("published"):
                failed = path.with_name(path.stem + ".failed-" + uuid.uuid4().hex + ".json")
                _record(failed, payload["record"])
                return {"path": str(failed)}
            shutil.copyfile(
                path, path.with_name(path.stem + ".prior-" + uuid.uuid4().hex + ".json")
            )
        _record(path, payload["record"])
        return {"path": str(path)}
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
    if operation == "sampling_controls":
        import hashlib

        from logo_maker.sampling import Settings, qualify_profile, validate_settings

        folder = Path(payload["concept_dir"])
        config = payload["config"]
        hashes = {}

        def load(name):
            if not name:
                return None
            path = Path(name)
            if not path.is_absolute():
                path = folder / path
            raw = path.read_bytes()
            hashes[str(path.resolve())] = hashlib.sha256(raw).hexdigest()
            data = json.loads(raw)
            for case in data.get("cases", []):
                evidence = case.get("evidence", {})
                if evidence.get("path"):
                    review = Path(evidence["path"])
                    evidence["path"] = str(
                        review if review.is_absolute() else (path.parent / review).resolve()
                    )
            return data

        profile = load(config.get("profile"))
        state, reason = qualify_profile(profile, payload["context"])
        effective = payload["quality"]
        overrides = effective.get("overrides", {})
        if state == "qualified" and profile:
            selected = profile["settings"]
            settings_keys = ("samples", "adaptive_threshold", "min_samples", "adaptive")
            for key in settings_keys:
                override_name = "max_samples" if key == "samples" else key
                if override_name not in overrides:
                    effective[key] = selected[key]
            conflicts = [
                key
                for key in settings_keys
                if effective.get(key, 0 if key == "min_samples" else None)
                != selected.get(key, 0 if key == "min_samples" else None)
            ]
            if conflicts:
                state, reason = (
                    "override_conflict",
                    "explicit controls outside qualified settings: " + ", ".join(conflicts),
                )
            # qualify_profile verified these exact expected hashes against the review files.
            for case in profile["cases"]:
                evidence = case["evidence"]
                hashes[evidence["path"]] = evidence["sha256"]
        validate_settings(Settings.from_quality(effective))
        diagnosis = load(config.get("diagnosis"))
        return {
            "profile": [state, reason],
            "quality": effective,
            "hashes": hashes,
            "diagnosis": diagnosis,
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
        import hashlib

        from logo_maker.render import _artifact_current_local

        folder = Path(payload["concept_dir"])
        try:
            raw = (folder / ".build" / f"{payload['quality']}.sampling.json").read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if (
                payload.get("expected_record_sha256")
                and payload["expected_record_sha256"] != digest
            ):
                return {"current": False}
            record = json.loads(raw)
        except (OSError, ValueError):
            return {"current": False}
        current = _artifact_current_local(folder, payload["quality"], record=record)
        return {"current": current, "context": record.get("context", {})}
    if operation == "qa_checks":
        from logo_maker import checks

        png = Path(payload["png"])
        return {
            "alpha": checks.alpha_report(png),
            "margin": checks.margin_report(png),
            "edges": checks.edge_report(png),
            "colors": checks.color_report(png, payload["palette"]),
        }
    if operation == "tiny_image":
        from logo_maker.judging import tiny_version

        dest = Path(payload["dest"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        tiny_version(Path(payload["png"]), dest)
        return {"prepared": True}
    raise ValueError(f"unknown host operation {operation!r}")


if __name__ == "__main__":
    print(json.dumps(main(json.loads(sys.stdin.read()))), flush=True)
