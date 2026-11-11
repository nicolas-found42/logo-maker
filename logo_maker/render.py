"""Host-side render orchestration: compile, run the bpy subprocess, retry once on a
crash, downsample finals, and hand non-Cycles exports to their renderer.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import tomllib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from logo_maker import owned_process
from logo_maker.host import run as _host_work
from logo_maker.proc import ToolError
from logo_maker.sampling import Budget, SamplingLimit, Settings, decide
from logo_maker.sampling_diagnostics import sha256

#: Seconds before a GPU render is declared stuck. Never kill earlier: the first
#: run compiles Metal kernels for 1.5-5 minutes with no output.
RENDER_TIMEOUT = 900.0

#: Blender 5.2.3 aborts intermittently on first Metal kernel load (issue #165570);
#: the cache it already wrote usually makes the retry succeed.
_CRASH_HINTS = ("SIGABRT", "Segmentation fault", "abort")


@dataclass(frozen=True)
class AssetUse:
    key: str
    source: str
    license: str
    path: str


@dataclass(frozen=True)
class RenderResult:
    png: Path
    blend: Path
    glb: Path
    seconds: float
    quality: str
    execution: Path | None = None
    sampling: Path | None = None
    assets: tuple[AssetUse, ...] = ()
    publication: dict | None = None


def _alpha_cleanup_png(png: Path) -> Path:
    """Clear background haze host-side: haze-level alpha (<= checks.VEIL_ALPHA_MAX)
    on the open background drops to 0, so the mark's anti-aliased edge stays intact.
    Headless pip bpy 5.2.3 exposes no compositor node tree, so this runs here."""
    import numpy as np
    from PIL import Image

    from logo_maker import checks

    with Image.open(png) as img:
        arr = np.array(img.convert("RGBA"))
    alpha = arr[..., 3]
    alpha[checks.open_background(alpha) & (alpha <= checks.VEIL_ALPHA_MAX)] = 0
    Image.fromarray(arr).save(png)
    return png


def content_key(data: object) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def machine_context(budget: Budget) -> dict:
    """Probe the installed bpy/device/library identity; no persistent timing cache."""
    budget.check()
    proc = subprocess.run(
        [sys.executable, "-m", "logo_maker.blender.profile"],
        capture_output=True,
        text=True,
        timeout=min(900, budget.remaining),
        check=False,
    )
    if proc.returncode:
        raise ToolError(f"GPU-only profile preflight failed: {proc.stderr[-2000:]}")
    budget.check()
    return json.loads(proc.stdout.strip().splitlines()[-1])


def control_paths(concept_dir: Path, config: dict) -> dict[str, Path]:
    """Policy records bind image evidence; they are not inputs to their own image key."""
    return {
        field: (concept_dir / config[field]).resolve()
        for field in ("profile", "diagnosis")
        if config.get(field)
    }


def source_files(concept_dir: Path) -> set[Path]:
    from logo_maker.refinement import concept_sources

    paths = set(concept_sources(concept_dir).values())
    brief = concept_dir.parent.parent / "brief.toml"
    if concept_dir.parent.name == "concepts" and brief.is_file():
        from logo_maker.brief import load

        paths.add(brief)
        paths.update(reference.path for reference in load(brief).references)
    package = Path(__file__).parent
    paths.update(package.rglob("*.py"))
    paths.update(package.rglob("*.toml"))
    paths.update(
        p for name in ("uv.lock", "pyproject.toml") if (p := package.parent / name).is_file()
    )
    recipe = concept_dir / "scene.toml"
    config = tomllib.loads(recipe.read_text()).get("sampling", {}) if recipe.exists() else {}
    return {p.resolve() for p in paths} - set(control_paths(concept_dir, config).values())


def dependency_hashes(concept_dir: Path, scene_data: dict) -> dict:
    """Bind source, compiled scene, meshes and resolved external assets by content."""
    paths = source_files(concept_dir)
    paths.update(p.resolve() for p in (concept_dir / ".build/meshes").rglob("*") if p.is_file())

    # Compiled JSON contains resolved font/HDRI/texture/mesh paths.
    def collect(value):
        if isinstance(value, dict):
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
        elif isinstance(value, str):
            path = Path(value)
            if path.is_absolute() and path.is_file():
                paths.add(path.resolve())

    collect({k: v for k, v in scene_data.items() if k != "sampling"})
    return {str(p): sha256(p) for p in sorted(paths)}


def render(
    concept_dir: Path | str,
    quality: str = "preview",
    on_asset: object = None,
    *,
    budget: Budget | None = None,
) -> RenderResult:
    """Render bounded candidates in quarantine; publish only a complete verified output.

    An unqualified baseline may be inspected, but is explicitly not a sampling
    acceptance. Finalize cannot call it a qualified winner.
    """
    concept_dir = Path(concept_dir).absolute()
    started = time.monotonic()
    caller_budget = budget
    completion_budget = budget or Budget()
    budget = Budget(parent=completion_budget, attempt_limit=completion_budget.attempt_limit)
    budget.deadline -= 2
    job_started = budget.clock()
    budget.check()
    build = concept_dir / ".build"
    job_path = build / f"{quality}.sampling.json"
    job: dict = {
        "schema": 1,
        "quality": quality,
        "published": False,
        "attempts": [],
        "host_stages": [],
        "outcomes": {
            "device": "unknown",
            "noise": "unknown",
            "cap": "unknown",
            "time": "within_budget",
            "memory": "unknown",
            "quality": "unreviewed",
        },
    }
    try:
        _host_work(
            {"operation": "render_setup", "concept_dir": str(concept_dir)},
            budget,
            job["host_stages"],
        )
        if on_asset is not None:
            raise ToolError(
                "budget_conflict: arbitrary on_asset callbacks cannot preserve parent-side effects "
                "inside a bounded worker; use the returned RenderResult.assets records instead"
            )
        config = _host_work(
            {"operation": "load_config", "concept_dir": str(concept_dir)},
            budget,
            job["host_stages"],
        )["sampling"]
        completion_budget = Budget(
            config["wall_seconds"],
            config["attempt_limit"],
            parent=caller_budget,
            clock=budget.clock,
            started_at=job_started,
        )
        budget = Budget(parent=completion_budget, attempt_limit=completion_budget.attempt_limit)
        budget.deadline -= 2
        budget.check()
        compiled = _host_work(
            {"operation": "compile", "concept_dir": str(concept_dir), "quality": quality},
            budget,
            job["host_stages"],
        )
        job["assets"] = compiled["assets"]
        budget.check()
        scene_data = compiled["scene"]
        renderer = scene_data["render"].get("renderer", "cycles")
        if renderer != "cycles":
            raise ToolError(f"GPU-only policy: {renderer} lacks verified GPU tracing and denoising")
        config = scene_data.get("sampling", {})
        budget = Budget(
            config.get("wall_seconds", 1800),
            config.get("attempt_limit", 2),
            parent=budget,
            started_at=job_started,
        )
        env = machine_context(budget)
        deps = compiled["dependencies"]
        render_scope = {
            k: v
            for k, v in scene_data["render"].items()
            if k not in {"max_samples", "min_samples", "seed", "adaptive_threshold", "adaptive"}
        }
        # Machine timing/quality scope transfers across reviewed materials and
        # normal geometry. Full recipe/assets/settings/seed still bind image evidence.
        context = {
            **env,
            "stage": quality,
            "resolution": scene_data["quality"]["resolution"],
            "settings_key": content_key(render_scope),
            "code_sha256": {
                str(Path(k).relative_to(Path(__file__).parent)): v
                for k, v in deps.items()
                if Path(k).is_relative_to(Path(__file__).parent)
            },
            "material_presets": sorted(
                {m.get("preset", "unknown") for m in scene_data.get("materials", {}).values()}
            ),
        }
        if any(o.get("kind") == "bpy" for o in scene_data.get("objects", [])):
            context["custom_scene_sha256"] = deps.get(str(concept_dir / "scene.py"), "unknown")
        controls = _host_work(
            {
                "operation": "sampling_controls",
                "concept_dir": str(concept_dir),
                "config": config,
                "context": context,
                "quality": scene_data["quality"],
            },
            budget,
            job["host_stages"],
        )
        effective = controls["quality"]
        scene_data["quality"] = effective
        overrides = effective.get("overrides", {})
        profile_state, reason = controls["profile"]
        job["control_files_sha256"] = controls["hashes"]
        job.update(
            context=context,
            profile={"state": profile_state, "reason": reason},
            dependencies=deps,
            overrides=overrides,
            source_key=content_key({"scene": scene_data, "dependencies": deps}),
        )
        diagnosis = controls["diagnosis"]
        while True:
            budget.check()
            candidate_started = time.monotonic()
            attempt_dir = build / ("attempt-" + uuid.uuid4().hex)
            scene_data["output_dir"] = str(attempt_dir)
            image_scene = {
                k: v
                for k, v in scene_data.items()
                if k not in {"sampling", "output_dir", "build_dir"}
            }
            source_key = content_key(
                {
                    "compiled_scene": image_scene,
                    "dependencies": {k: v for k, v in deps.items() if Path(k).name != "scene.toml"},
                    "context": context,
                }
            )
            candidate_json = attempt_dir / "scene.json"
            # Meshes are relative to the original build directory; keep that explicit.
            scene_data["build_dir"] = str(build)
            _host_work(
                {"operation": "render_attempt", "directory": str(attempt_dir), "scene": scene_data},
                budget,
                job["host_stages"],
            )
            job["active_attempt"] = {
                "directory": str(attempt_dir),
                "compiled_scene": str(candidate_json),
                "execution": str(attempt_dir / f"{quality}.execution.json"),
            }
            _run_builder(candidate_json, concept_dir, quality, budget=budget)
            evidence_path = attempt_dir / f"{quality}.execution.json"
            execution_info = _host_work(
                {"operation": "render_execution", "path": str(evidence_path)},
                budget,
                job["host_stages"],
            )
            execution = execution_info["record"]
            if execution.get("status") != "verified":
                raise ToolError("GPU-only rendering/denoising unverified")
            png = attempt_dir / f"{quality}.png"
            renderer = scene_data["render"].get("renderer", "cycles")
            if renderer != "cycles":
                budget.begin_attempt()
                command = [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; from logo_maker.render import _run_alternate; "
                    "import sys; print(_run_alternate(sys.argv[1], Path(sys.argv[2]), sys.argv[3], int(sys.argv[4])))",
                    renderer,
                    str(attempt_dir),
                    quality,
                    str(effective["resolution"]),
                ]
                proc = owned_process.run(
                    command, budget=budget, label="explicit alternate renderer"
                )
                if proc.returncode:
                    raise ToolError(f"explicit alternate renderer failed: {proc.stderr[-2000:]}")
                png = attempt_dir / f"{quality}.png"
            processed = _host_work(
                {
                    "operation": "process_image",
                    "png": str(png),
                    "quality": quality,
                    "alpha_cleanup": bool(scene_data["render"].get("alpha_cleanup")),
                    "exr": str(evidence_path.with_suffix(".exr")),
                    "cap": effective["samples"],
                    "max_bytes": config.get("diagnostic_bytes", 2147483648),
                },
                budget,
                job["host_stages"],
            )
            diagnostics: dict = processed["diagnostics"]
            if renderer != "cycles":
                diagnostics = {
                    "status": "unknown",
                    "reason": "explicit alternate output outside Cycles sampling qualification",
                }
            budget.check()
            delivered_hash = processed["delivered_sha256"]
            elapsed = time.monotonic() - candidate_started
            decision = decide(
                Settings.from_quality(effective),
                diagnosis,
                source_key=source_key,
                image_sha256=delivered_hash,
                diagnostics=diagnostics,
                overrides=overrides,
                attempts_left=budget.attempt_limit - budget.attempts,
                seconds_left=budget.remaining,
                estimated_seconds=elapsed * 2,
            )
            if profile_state != "qualified" and decision.state == "compare":
                from logo_maker.sampling import Decision

                decision = Decision(
                    "profile_unqualified", "comparison requires qualified machine profile"
                )
            foreground = diagnostics.get("regions", {}).get("foreground") or {}
            job["outcomes"].update(
                device="verified" if renderer == "cycles" else "outside_cycles_policy",
                cap=(
                    "capped"
                    if foreground.get("near_cap_fraction", 0) > 0
                    else "not_near_cap"
                    if foreground
                    else "unknown"
                ),
            )
            attempt = {
                "source_key": source_key,
                "quality": dict(effective),
                "execution": str(evidence_path),
                "execution_sha256": execution_info["sha256"],
                "delivered_sha256": delivered_hash,
                "diagnostics": diagnostics,
                "seconds": elapsed,
                "decision": decision.record(),
            }
            job["attempts"].append(attempt)
            job.pop("active_attempt", None)
            job["outcomes"]["noise"] = decision.state
            job["outcomes"]["sampling"] = (
                "profile_baseline"
                if profile_state == "qualified"
                and diagnosis is None
                and len(job["attempts"]) == 1
                and diagnostics.get("status") == "available"
                else "review_needed"
            )
            # Retain every comparison. New evidence must bind the next image; a
            # previous image's diagnosis cannot recursively escalate the next one.
            if decision.state == "compare" and decision.settings:
                effective.update(decision.settings.quality())
                diagnosis = None
                continue
            job.update(
                published=True,
                delivered_sha256=delivered_hash,
                source_key=source_key,
                execution=str(evidence_path),
                execution_sha256=execution_info["sha256"],
            )
            job["budget"] = completion_budget.record()
            job["seconds"] = time.monotonic() - started
            job["timing_scope"] = (
                "through publication staging; RenderResult.seconds includes publication, recovery/cleanup and return"
            )
            publication = publish_artifacts(attempt_dir, concept_dir, quality, budget, record=job)
            break
    except Exception as exc:
        message = str(exc)
        job["published"] = False
        job["error"] = message
        if "budget_conflict" in message:
            job["outcomes"]["time"] = "budget_conflict"
        elif isinstance(exc, (SamplingLimit, subprocess.TimeoutExpired)):
            job["outcomes"]["time"] = (
                "time_limit" if "attempt_limit" not in message else "attempt_limit"
            )
        elif "GPU" in message or "denois" in message or "Metal" in message:
            job["outcomes"]["device"] = "failed"
        elif "memory" in message.lower():
            job["outcomes"]["memory"] = "failed"
        raise
    finally:
        if budget.remaining <= 0:
            job["outcomes"]["time"] = "time_limit"
        job["budget"] = completion_budget.record()
        job["seconds"] = time.monotonic() - started
        job["timing_scope"] = (
            "configuration, compile/dependency hashes, environment probe, all attempts/denoise/diagnostic IO/downsample/hash; excludes caller QA and export"
        )
        if not job["published"] and completion_budget.remaining > 1:
            _host_work(
                {"operation": "render_record", "path": str(job_path), "record": job},
                completion_budget,
                job["host_stages"],
            )
    return RenderResult(
        concept_dir / f"{quality}.png",
        concept_dir / "scene.blend",
        concept_dir / "model.glb",
        time.monotonic() - started,
        quality,
        Path(job["execution"])
        if scene_data["render"].get("renderer", "cycles") == "cycles"
        else None,
        job_path,
        tuple(AssetUse(**asset) for asset in job.get("assets", [])),
        publication,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(concept_dir: Path) -> dict[str, str]:
    return {
        name: _sha256(concept_dir / name)
        for name in ("scene.toml", "motif.json", "scene.py")
        if (concept_dir / name).is_file()
    }


def verify_execution(concept_dir: Path, quality: str) -> dict:
    """Reject cached, altered, alternate or unverified outputs operationally."""
    from logo_maker.blender.execution import verify_denoiser_log

    sampling_path = concept_dir / ".build" / f"{quality}.sampling.json"
    sampling = json.loads(sampling_path.read_text()) if sampling_path.is_file() else None
    if sampling is not None and not _artifact_current_local(concept_dir, quality, record=sampling):
        raise ToolError(
            f"GPU-only execution evidence unavailable/invalid for {quality}: stale render provenance"
        )
    evidence = (
        Path(sampling["execution"])
        if sampling
        else concept_dir / ".build" / f"{quality}.execution.json"
    )
    try:
        report = json.loads(evidence.read_text())
        selected = [d for d in report["devices"] if d["use"]]
        if not (
            report["status"] == "verified"
            and report["policy"] == "metal-gpu-only"
            and report["device_override"] == "METAL"
            and len(selected) == 1
            and selected[0]["type"] == "METAL"
            and report["denoiser_effective"]["device_type"] == "Metal"
            and (
                sampling is not None
                or (
                    report["host_sources_sha256"] == source_hashes(concept_dir)
                    and report["delivered_sha256"] == _sha256(concept_dir / f"{quality}.png")
                )
            )
        ):
            raise ValueError("stale or invalid execution attestation")
        log = evidence.with_suffix(".log")
        if report["log_sha256"] != _sha256(log):
            raise ValueError("changed runtime log")
        verify_denoiser_log(log.read_text())
        compiled = evidence.parent / ("scene.json" if sampling else f"{quality}.json")
        compiled_scene = json.loads(compiled.read_text())
        build_dir = Path(compiled_scene.get("build_dir", evidence.parent))
        for name, digest in report["inputs_sha256"].items():
            path = compiled if name == "compiled_scene" else build_dir / name
            if _sha256(path) != digest:
                raise ValueError(f"changed render input: {name}")
        if not report.get("sampling"):
            raise ValueError("missing effective sampling settings")
    except (OSError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise ToolError(
            f"GPU-only execution evidence unavailable/invalid for {quality}: {exc}"
        ) from exc
    return {**report, "evidence_path": str(evidence)}


def publish_artifacts(
    attempt_dir: Path,
    concept_dir: Path,
    quality: str,
    budget: Budget,
    *,
    record: dict | None = None,
) -> dict:
    """Own blocking copies and recover interrupted publication within the deadline."""
    from logo_maker.publication import publish

    entries = [
        {"source": str(attempt_dir / name), "target": str(concept_dir / name), "optional": True}
        for name in ("scene.blend", "model.glb", f"{quality}.png")
    ]
    journal = concept_dir / ".build" / ("publication-" + uuid.uuid4().hex + ".json")
    if record is not None:
        record["publication"] = {
            "journal": str(journal),
            "cleanup": "journal retained until cleanup completes",
        }
        entries.append(
            {
                "target": str(concept_dir / ".build" / f"{quality}.sampling.json"),
                "text": json.dumps(record, indent=2) + "\n",
            }
        )
    return publish(
        entries,
        journal,
        budget,
        [],
    )


def _run_builder(scene_json: Path, concept_dir: Path, quality: str, *, budget: Budget) -> None:
    cmd = [sys.executable, "-m", "logo_maker.blender.build", str(scene_json)]
    for retry in range(2):
        attempt = budget.begin_attempt()
        proc = owned_process.run(
            cmd,
            budget=budget,
            timeout=RENDER_TIMEOUT,
            cwd=Path.cwd(),
            label=f"bpy attempt {attempt}",
        )
        if proc.returncode == 0:
            budget.check()
            return
        tail = (proc.stderr or proc.stdout or "")[-2000:]
        crashed = proc.returncode in (-6, -11, 134, 139) or any(h in tail for h in _CRASH_HINTS)
        if crashed and retry == 0:
            continue
        raise ToolError(f"bpy build exited {proc.returncode} (attempt {attempt}): {tail}")
    raise ToolError(f"bpy build failed twice: {concept_dir.name}")


def _run_alternate(renderer: str, concept_dir: Path, quality: str, resolution: int) -> Path:
    """Render the bpy-written export with the matching alternate renderer."""
    import importlib

    try:
        module = importlib.import_module(f"logo_maker.renderers.{renderer}")
    except ImportError as exc:
        raise ToolError(f"renderer {renderer!r} has no logo_maker.renderers module: {exc}") from exc
    out_png = concept_dir / f"{quality}.png"
    return Path(
        module.render(
            concept_dir / "meshes" / "scene_export.json",
            out_png,
            quality=quality,
            resolution=resolution,
        )
    )


def _downsample_final(png: Path) -> Path:
    """Lanczos-3 the 4000 px final to 2000 px in place, keeping alpha."""
    import OpenImageIO as oiio

    buf = oiio.ImageBuf(str(png))
    spec = buf.spec()
    if spec.width <= 2000:
        return png
    out = oiio.ImageBuf(oiio.ImageSpec(2000, 2000, spec.nchannels, spec.format))
    if not oiio.ImageBufAlgo.resize(out, buf, filtername="lanczos3"):
        raise ToolError(f"downsampling {png} failed: {out.geterror()}")
    tmp = png.with_name(f"{png.stem}.downsampled.png")
    if not out.write(str(tmp)):
        raise ToolError(f"writing {tmp} failed: {out.geterror()}")
    tmp.replace(png)
    return png


def render_many(
    concept_dirs: Sequence[Path | str], quality: str = "preview", workers: int | None = None
) -> list[RenderResult]:
    """Run one bounded concept job at a time; workers remains a compatibility argument.

    Compilation belongs to each job's deadline, rather than an unbounded prepass.
    """
    dirs = [Path(d) for d in concept_dirs]
    return [render(d, quality) for d in dirs]


def artifact_current(
    concept_dir: Path,
    quality: str,
    *,
    check_machine: bool = True,
    budget: Budget | None = None,
    expected_record_sha256: str | None = None,
) -> bool:
    """Production reuse requires complete supported sampling/runtime scope."""
    return _artifact_current(
        concept_dir,
        quality,
        check_machine=check_machine,
        budget=budget,
        expected_record_sha256=expected_record_sha256,
    )


def inspection_artifact_current(
    concept_dir: Path, quality: str, *, budget: Budget | None = None
) -> bool:
    """Reopen retained previews for critique without granting production reuse/qualification."""
    return _artifact_current(
        concept_dir, quality, budget=budget, inspection_only=quality == "preview"
    )


def _artifact_current(
    concept_dir: Path,
    quality: str,
    *,
    check_machine: bool = True,
    budget: Budget | None = None,
    inspection_only: bool = False,
    expected_record_sha256: str | None = None,
) -> bool:
    """Content freshness includes source, code, devices, seed, execution and delivered bytes."""
    budget = budget or Budget()
    budget.check()
    snapshot = _host_work(
        {
            "operation": "artifact_current",
            "concept_dir": str(concept_dir),
            "quality": quality,
            "expected_record_sha256": expected_record_sha256,
            "inspection_only": inspection_only,
        },
        budget,
        [],
    )
    if not snapshot["current"]:
        return False
    if check_machine:
        env = machine_context(budget)
        if any(snapshot["context"].get(k) != v for k, v in env.items()):
            return False
    budget.check()
    return True


def _artifact_current_local(
    concept_dir: Path, quality: str, *, record: dict | None = None, inspection_only: bool = False
) -> bool:
    """Disk/hash work only; called by the owned host worker."""
    try:
        if record is None:
            record = json.loads((concept_dir / ".build" / f"{quality}.sampling.json").read_text())
        if "custom_scene_sha256" in record.get("context", {}) and not (
            inspection_only and quality == "preview"
        ):
            return False
        if (
            not record["published"]
            or sha256(concept_dir / f"{quality}.png") != record["delivered_sha256"]
        ):
            return False
        if any(
            not Path(p).is_file() or sha256(Path(p)) != digest
            for p, digest in record["dependencies"].items()
        ):
            return False
        if not {str(p) for p in source_files(concept_dir)} <= set(record["dependencies"]):
            return False
        if any(
            not Path(p).is_file() or sha256(Path(p)) != digest
            for p, digest in record.get("control_files_sha256", {}).items()
        ):
            return False
        evidence = Path(record["execution"])
        if sha256(evidence) != record["execution_sha256"]:
            return False
        return json.loads(evidence.read_text()).get("status") == "verified"
    except (OSError, KeyError, ValueError, ToolError):
        return False
