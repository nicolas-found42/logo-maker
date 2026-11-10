"""Host-side render orchestration: compile, run the bpy subprocess, retry once on a
crash, downsample finals, and hand non-Cycles exports to their renderer.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from logo_maker.proc import ToolError

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


def render(
    concept_dir: Path | str, quality: str = "preview", on_asset: object = None
) -> RenderResult:
    """Compile `concept_dir` and render it; returns PNG/blend/glb paths and wall time."""
    from logo_maker import scene as scene_mod

    concept_dir = Path(concept_dir)
    started = time.monotonic()
    scene_json = scene_mod.compile(concept_dir, quality, on_asset=on_asset)
    scene_data = json.loads(scene_json.read_text())
    renderer = scene_data["render"].get("renderer", "cycles")
    if renderer != "cycles":
        raise ToolError(f"GPU-only policy: {renderer} lacks verified GPU tracing and denoising")
    sources = source_hashes(concept_dir)
    snapshot = concept_dir / ".build" / f"{quality}.json"
    snapshot.write_bytes(scene_json.read_bytes())
    scene_json = snapshot
    _run_builder(scene_json, concept_dir, quality)
    name = scene_data["quality"]["name"]
    png = concept_dir / f"{name}.png"
    if quality == "final":
        png = _downsample_final(png)
    if scene_data["render"].get("alpha_cleanup"):
        png = _alpha_cleanup_png(png)
    evidence = concept_dir / ".build" / f"{name}.execution.json"
    report = json.loads(evidence.read_text())
    report["delivered_sha256"] = _sha256(png)
    report["host_sources_sha256"] = sources
    evidence.write_text(json.dumps(report, indent=2) + "\n")
    verify_execution(concept_dir, quality)
    seconds = time.monotonic() - started
    return RenderResult(
        png=png,
        blend=concept_dir / "scene.blend",
        glb=concept_dir / "model.glb",
        seconds=seconds,
        quality=quality,
        execution=concept_dir / ".build" / f"{name}.execution.json",
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

    evidence = concept_dir / ".build" / f"{quality}.execution.json"
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
            and report["host_sources_sha256"] == source_hashes(concept_dir)
            and report["delivered_sha256"] == _sha256(concept_dir / f"{quality}.png")
        ):
            raise ValueError("stale or invalid execution attestation")
        log = evidence.with_suffix(".log")
        if report["log_sha256"] != _sha256(log):
            raise ValueError("changed runtime log")
        verify_denoiser_log(log.read_text())
        for name, digest in report["inputs_sha256"].items():
            path = evidence.parent / (f"{quality}.json" if name == "compiled_scene" else name)
            if _sha256(path) != digest:
                raise ValueError(f"changed render input: {name}")
        if not report.get("sampling"):
            raise ValueError("missing effective sampling settings")
    except (OSError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise ToolError(
            f"GPU-only execution evidence unavailable/invalid for {quality}: {exc}"
        ) from exc
    return report


def _run_builder(scene_json: Path, concept_dir: Path, quality: str) -> None:
    cmd = [sys.executable, "-m", "logo_maker.blender.build", str(scene_json)]
    for attempt in (1, 2):
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=RENDER_TIMEOUT, cwd=Path.cwd()
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolError(
                f"bpy render timed out after {RENDER_TIMEOUT:.0f}s "
                f"(attempt {attempt}): {concept_dir.name}"
            ) from exc
        if proc.returncode == 0:
            return
        tail = (proc.stderr or proc.stdout or "")[-2000:]
        crashed = proc.returncode in (-6, -11, 134, 139) or any(
            hint in tail for hint in _CRASH_HINTS
        )
        if crashed and attempt == 1:
            print(f"bpy crashed ({proc.returncode}); retrying once with the warm kernel cache")
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
