"""Verified campaign renders and content-addressed reuse of completed views."""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from logo_maker import host, owned_process
from logo_maker.sampling import Budget
from logo_maker.sampling_diagnostics import sha256 as file_hash

CONTROLS = {"samples": 8192, "adaptive_threshold": 0.01, "min_samples": 0}


def digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def code_identity() -> dict:
    root = Path(__file__).parent
    return {
        p.relative_to(root).as_posix(): file_hash(p)
        for p in sorted(root.rglob("*"))
        if p.suffix in {".py", ".toml"}
    }


def environment(budget: Budget) -> dict:
    result = owned_process.run(
        [sys.executable, "-m", "logo_maker.blender.study"],
        input_text=json.dumps({"operation": "environment"}),
        budget=budget,
        timeout=120,
        label="campaign environment",
    )
    if result.returncode:
        details = host.failure(result.stderr or result.stdout)
        raise RuntimeError(
            f"bundled bpy Metal probe exited {result.returncode}; run doctor in the render host. {details}"
        )
    runtime = json.loads(result.stdout.splitlines()[-1])
    if codex_digest := os.environ.get("LOGO_MAKER_CODEX_RUNTIME_SHA256"):
        runtime["codex_runtime_sha256"] = codex_digest
    return {"runtime": runtime, "code": code_identity()}


def _verified(folder: Path, files: dict) -> bool:
    return bool(files) and all(
        Path(name).name == name and (folder / name).is_file() and file_hash(folder / name) == value
        for name, value in files.items()
    )


def _matches(report: dict, name: str, files: dict, source: str) -> bool:
    inputs = report.get("inputs_sha256", {})
    expected = {
        f"{name}.png": report.get("png_sha256"),
        f"{name}-execution.log": report.get("log_sha256"),
    }
    if name == "hero-transparent":
        expected["scene.blend"] = inputs.get("editable_scene")
    return (
        verified_execution(report, name)
        and inputs.get("source") == source
        and all(digest and files.get(file) == digest for file, digest in expected.items())
    )


def render(source, compiled, out, name, budget, *, options, cache=None, diagnostics=False):
    large = name in {
        "hero-transparent",
        "independent-seed",
        "lower-threshold",
        "degraded-threshold",
    }
    payload = {
        "source": str(source),
        "compiled": compiled,
        "output": str(out),
        "view": name,
        "resolution": 4000 if large else 1000,
        "downsample": large,
        "diagnostics": diagnostics,
        "authored_cameras": True,
        **CONTROLS,
    }
    inputs = {"source": file_hash(source)}
    if compiled:
        inputs.update(
            {p.name: file_hash(p) for p in sorted((source.parent / "meshes").glob("*.ply"))}
        )
    identity = {
        "inputs": inputs,
        "environment": options,
        "render": {k: v for k, v in payload.items() if k not in {"source", "output"}},
    }
    key = digest(identity)
    cached = cache / key if cache else None
    progress = getattr(budget, "render_progress", None)
    if progress:
        progress(out.name, name, "rendering")
    if cached and (cached / "cache.json").is_file():
        try:
            row = json.loads((cached / "cache.json").read_text())
            report = json.loads((cached / f"{name}-execution.json").read_text())
            if (
                row.get("identity") == identity
                and _verified(cached, row.get("files", {}))
                and _matches(report, name, row["files"], inputs["source"])
            ):
                for file in row["files"]:
                    shutil.copyfile(cached / file, out / file)
                if progress:
                    progress(out.name, name, "verified", cache_key=key, reused=True)
                return report
        except (OSError, AttributeError, TypeError, ValueError):
            pass  # Only a complete, verified cache entry can save a render.
    budget.begin_attempt()
    try:
        result = owned_process.run(
            [sys.executable, "-m", "logo_maker.blender.study"],
            input_text=json.dumps(payload),
            budget=budget,
            timeout=900,
            label=f"campaign {name}",
        )
        if result.returncode:
            raise RuntimeError(host.failure(result.stderr or result.stdout))
        report = json.loads(result.stdout.splitlines()[-1])
        files = {p.name: file_hash(p) for p in out.glob(f"{name}*") if p.is_file()}
        if name == "hero-transparent":
            files["scene.blend"] = file_hash(out / "scene.blend")
        if not _matches(report, name, files, inputs["source"]):
            raise RuntimeError(f"campaign {name}: execution evidence does not match the files")
    except Exception as exc:
        if progress:
            progress(out.name, name, "failed", detail=str(exc).splitlines()[0])
        raise
    if cached and cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".view-", dir=cache) as temporary:
            staging = Path(temporary)
            for file in files:
                shutil.copyfile(out / file, staging / file)
            row = {"identity": identity, "files": files}
            (staging / "cache.json").write_text(json.dumps(row, indent=2) + "\n")
            if cached.exists():
                shutil.rmtree(cached)
            staging.rename(cached)
    if progress:
        progress(out.name, name, "verified", cache_key=key, reused=False)
    return report


def verified_execution(report: dict, name: str) -> bool:
    sampling = report.get("sampling", {})
    threshold = {"lower-threshold": 0.005, "degraded-threshold": 0.02}.get(name, 0.01)
    large = name in {
        "hero-transparent",
        "independent-seed",
        "lower-threshold",
        "degraded-threshold",
    }
    return (
        report.get("status") == "verified"
        and report.get("device_override") == "METAL"
        and [d.get("type") for d in report.get("devices", []) if d.get("use")] == ["METAL"]
        and report.get("denoiser_effective", {}).get("device_type") == "Metal"
        and sampling.get("samples") == CONTROLS["samples"]
        and sampling.get("adaptive_min_samples") == CONTROLS["min_samples"]
        and sampling.get("use_adaptive_sampling") is True
        and math.isclose(sampling.get("adaptive_threshold", 0), threshold, abs_tol=1e-8)
        and report.get("resolution") == [4000 if large else 1000] * 2
        and (not large or report.get("delivery_resolution") == 2000)
    )
