"""Host-side render orchestration: compile, run the bpy subprocess, retry once on a
crash, downsample finals, and hand non-Cycles exports to their renderer.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from logo_maker.proc import ToolError
from logo_maker.sampling import Budget, SamplingLimit, Settings, decide, qualify_profile
from logo_maker.sampling_diagnostics import analyze_exr, sha256

#: Seconds before a GPU render is declared stuck. Never kill earlier: the first
#: run compiles Metal kernels for 1.5-5 minutes with no output.
RENDER_TIMEOUT = 900.0

#: Blender 5.2.3 aborts intermittently on first Metal kernel load (issue #165570);
#: the cache it already wrote usually makes the retry succeed.
_CRASH_HINTS = ("SIGABRT", "Segmentation fault", "abort")


@dataclass(frozen=True)
class RenderResult:
    png: Path
    blend: Path
    glb: Path
    seconds: float
    quality: str
    execution: Path | None = None
    sampling: Path | None = None


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


def source_files(concept_dir: Path) -> set[Path]:
    names = ("scene.toml", "motif.json", "motif.svg", "concept.json")
    paths = {concept_dir / name for name in names if (concept_dir / name).is_file()}
    paths.update(concept_dir.glob("*.py"))
    package = Path(__file__).parent
    paths.update(package.rglob("*.py"))
    paths.update(package.rglob("*.toml"))
    paths.update(
        p for name in ("uv.lock", "pyproject.toml") if (p := package.parent / name).is_file()
    )
    return {p.resolve() for p in paths}


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

    collect(scene_data)
    return {str(p): sha256(p) for p in sorted(paths)}


def _load_optional(folder: Path, name: str | None) -> dict | None:
    if not name:
        return None
    path = Path(name)
    if not path.is_absolute():
        path = folder / path
    data = json.loads(path.read_text())
    for case in data.get("cases", []):
        evidence = case.get("evidence", {})
        if evidence.get("path"):
            review = Path(evidence["path"])
            evidence["path"] = str(
                review if review.is_absolute() else (path.parent / review).resolve()
            )
    return data


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
    from logo_maker import scene as scene_mod

    concept_dir = Path(concept_dir).resolve()
    started = time.monotonic()
    if budget:
        budget.check()
    else:
        config = scene_mod.load_scene(concept_dir / "scene.toml")["sampling"]
        budget = Budget(config["wall_seconds"], config["attempt_limit"])
    build = concept_dir / ".build"
    build.mkdir(exist_ok=True)
    job_path = build / f"{quality}.sampling.json"
    job: dict = {
        "schema": 1,
        "quality": quality,
        "published": False,
        "attempts": [],
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
        scene_json = scene_mod.compile(concept_dir, quality, on_asset=on_asset)
        budget.check()
        scene_data = json.loads(scene_json.read_text())
        config = scene_data.get("sampling", {})
        budget = Budget(
            config.get("wall_seconds", 1800), config.get("attempt_limit", 2), parent=budget
        )
        env = machine_context(budget)
        deps = dependency_hashes(concept_dir, scene_data)
        controls = {}
        for field in ("profile", "diagnosis"):
            if config.get(field):
                control = Path(config[field])
                if not control.is_absolute():
                    control = concept_dir / control
                controls[str(control.resolve())] = sha256(control)
        job["control_files_sha256"] = controls
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
        profile = _load_optional(concept_dir, config.get("profile"))
        profile_state, reason = qualify_profile(profile, context)
        effective = scene_data["quality"]
        overrides = effective.get("overrides", {})
        if profile_state == "qualified" and profile:
            selected = profile["settings"]
            for key in ("samples", "adaptive_threshold", "min_samples", "adaptive"):
                override_name = "max_samples" if key == "samples" else key
                if override_name not in overrides:
                    effective[key] = selected[key]
            conflicts = [
                k
                for k in ("samples", "adaptive_threshold", "min_samples", "adaptive")
                if effective.get(k, 0 if k == "min_samples" else None)
                != selected.get(k, 0 if k == "min_samples" else None)
            ]
            if conflicts:
                profile_state, reason = (
                    "override_conflict",
                    "explicit controls outside qualified settings: " + ", ".join(conflicts),
                )
            for case in profile.get("cases", []):
                evidence = case.get("evidence", {})
                if evidence.get("path"):
                    controls[evidence["path"]] = sha256(Path(evidence["path"]))
        from logo_maker.sampling import validate_settings

        validate_settings(Settings.from_quality(effective))
        job.update(
            context=context,
            profile={"state": profile_state, "reason": reason},
            dependencies=deps,
            overrides=overrides,
            source_key=content_key({"scene": scene_data, "dependencies": deps}),
        )
        diagnosis = _load_optional(concept_dir, config.get("diagnosis"))
        while True:
            budget.check()
            candidate_started = time.monotonic()
            attempt_dir = build / ("attempt-" + uuid.uuid4().hex)
            attempt_dir.mkdir()
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
            candidate_json.write_text(json.dumps(scene_data, indent=2))
            _run_builder(candidate_json, concept_dir, quality, budget=budget)
            evidence_path = attempt_dir / f"{quality}.execution.json"
            execution = json.loads(evidence_path.read_text())
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
                proc = subprocess.run(
                    command, capture_output=True, text=True, timeout=budget.remaining, check=False
                )
                if proc.returncode:
                    raise ToolError(f"explicit alternate renderer failed: {proc.stderr[-2000:]}")
                png = attempt_dir / f"{quality}.png"
            if quality == "final":
                _downsample_final(png)
            if scene_data["render"].get("alpha_cleanup"):
                _alpha_cleanup_png(png)
            diagnostics: dict = analyze_exr(
                evidence_path.with_suffix(".exr"),
                cap=effective["samples"],
                max_bytes=config.get("diagnostic_bytes", 2147483648),
            )
            if renderer != "cycles":
                diagnostics = {
                    "status": "unknown",
                    "reason": "explicit alternate output outside Cycles sampling qualification",
                }
            budget.check()
            delivered_hash = sha256(png)
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
                "execution_sha256": sha256(evidence_path),
                "delivered_sha256": delivered_hash,
                "diagnostics": diagnostics,
                "seconds": elapsed,
                "decision": decision.record(),
            }
            job["attempts"].append(attempt)
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
            publish_artifacts(attempt_dir, concept_dir, quality, budget)
            job.update(
                published=True,
                delivered_sha256=delivered_hash,
                source_key=source_key,
                execution=str(evidence_path),
                execution_sha256=sha256(evidence_path),
            )
            break
    except Exception as exc:
        message = str(exc)
        job["error"] = message
        if isinstance(exc, (SamplingLimit, subprocess.TimeoutExpired)):
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
        job["budget"] = budget.record()
        job["seconds"] = time.monotonic() - started
        job["timing_scope"] = (
            "compile, environment probe, all attempts/denoise/diagnostic IO/downsample/hash; excludes caller QA and export"
        )
        if job_path.exists():
            shutil.copyfile(
                job_path, build / (quality + ".prior-" + uuid.uuid4().hex + ".sampling.json")
            )
        job_path.write_text(json.dumps(job, indent=2) + "\n")
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
    )


def publish_artifacts(attempt_dir: Path, concept_dir: Path, quality: str, budget: Budget) -> None:
    """Stage all I/O before committing, with rollback if publication hits its limit."""
    token = uuid.uuid4().hex
    staged = {}
    backups = {}
    committed = []
    succeeded = False
    try:
        for name in ("scene.blend", "model.glb", f"{quality}.png"):
            source = attempt_dir / name
            if source.exists():
                budget.check()
                target = concept_dir / name
                temp = concept_dir / (".publishing-" + token + "-" + name)
                staged[target] = temp
                shutil.copyfile(source, temp)
        budget.check()
        for target, temp in staged.items():
            if target.exists():
                backup = target.with_name(".prior-" + token + "-" + target.name)
                target.replace(backup)
                backups[target] = backup
            temp.replace(target)
            committed.append(target)
            budget.check()
        succeeded = True
    except BaseException:
        for target in committed:
            target.unlink(missing_ok=True)
        for target, backup in backups.items():
            backup.replace(target)
        raise
    finally:
        for path in staged.values():
            path.unlink(missing_ok=True)
        if succeeded:
            for path in backups.values():
                path.unlink(missing_ok=True)


def _run_builder(scene_json: Path, concept_dir: Path, quality: str, *, budget: Budget) -> None:
    cmd = [sys.executable, "-m", "logo_maker.blender.build", str(scene_json)]
    for retry in range(2):
        attempt = budget.begin_attempt()
        timeout = min(RENDER_TIMEOUT, budget.remaining)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, cwd=Path.cwd()
            )
        except subprocess.TimeoutExpired as exc:
            raise SamplingLimit(
                f"time_limit: bpy exceeded {timeout:.1f}s (attempt {attempt})"
            ) from exc
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


def _compile_one(args: tuple[str, str]) -> str:
    from logo_maker import scene as scene_mod

    concept_dir, quality = args
    return str(scene_mod.compile(Path(concept_dir), quality))


def render_many(
    concept_dirs: Sequence[Path | str], quality: str = "preview", workers: int | None = None
) -> list[RenderResult]:
    """Compile every concept across CPU cores first, then render on the GPU in turn."""
    import multiprocessing as mp

    ctx = mp.get_context("fork") if "fork" in mp.get_all_start_methods() else None
    dirs = [Path(d) for d in concept_dirs]
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
        list(pool.map(_compile_one, [(str(d), quality) for d in dirs]))
    return [render(d, quality) for d in dirs]


def artifact_current(
    concept_dir: Path, quality: str, *, check_machine: bool = True, budget: Budget | None = None
) -> bool:
    """Content freshness includes source, code, devices, seed, execution and delivered bytes."""
    if budget:
        budget.check()
    try:
        record = json.loads((concept_dir / ".build" / f"{quality}.sampling.json").read_text())
        if "custom_scene_sha256" in record.get("context", {}):
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
        if json.loads(evidence.read_text()).get("status") != "verified":
            return False
        if check_machine:
            env = machine_context(budget or Budget())
            if any(record["context"].get(k) != v for k, v in env.items()):
                return False
        return True
    except (OSError, KeyError, ValueError, ToolError):
        return False
