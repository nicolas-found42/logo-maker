"""`logo-maker doctor`: one line per adapter and environment check, with the fix for anything red."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from logo_maker.adapters import doctor as adapter_doctor

GPU_PROBE = """
from logo_maker.blender.metal import require_metal_device

try:
    require_metal_device()
except (RuntimeError, OSError) as exc:
    raise SystemExit(str(exc)) from None

import bpy
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"
prefs.refresh_devices()
names = [d.name for d in prefs.devices if d.type == "METAL"]
print("METAL:" + "|".join(names))
"""


def _gpu() -> str | None:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", GPU_PROBE],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "bpy GPU probe timed out after 120 s"
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("METAL:")), None)
    if proc.returncode or line is None:
        message = (proc.stderr or proc.stdout).strip()[-300:]
        return f"bundled bpy Metal probe exited {proc.returncode}" + (
            f": {message}" if message else ""
        )
    return None if line[6:] else "no Metal GPU device visible to Cycles"


def _jev_key() -> str | None:
    if os.environ.get("TYPESAFE_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
        return None
    return "set OPENROUTER_API_KEY (or TYPESAFE_API_KEY) for jev judgments"


def _kernels() -> str | None:
    cache = Path.home() / ".cache" / "cycles"
    if cache.is_dir() and any(cache.rglob("*")):
        return None
    return "Metal kernels not compiled yet; first render waits 1.5-5 min"


def _node() -> str | None:
    if shutil.which("node") is None:
        return "node not on PATH"
    try:
        out = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, check=False, timeout=15
        ).stdout.strip()
    except subprocess.TimeoutExpired:
        return "node --version timed out after 15 s"
    major = out.lstrip("v").split(".")[0]
    if not major.isdigit():
        return f"cannot read a node version from {out!r}"
    return None if int(major) >= 24 else f"node {out} is older than 24"


def _cache() -> str | None:
    from logo_maker.paths import cache_dir

    try:
        cache_dir()
    except RuntimeError as exc:
        return str(exc)
    return None


ENV_CHECKS: list[tuple[str, Callable[[], str | None], str]] = [
    ("jev API key", _jev_key, "export OPENROUTER_API_KEY=..."),
    ("Node.js >= 24", _node, "brew install node@24"),
    (
        "Cycles Metal GPU",
        _gpu,
        "check Metal access in the same Apple Silicon environment as the render",
    ),
    ("Metal kernel cache", _kernels, "just warm-gpu"),
    ("download cache", _cache, "unset LOGO_MAKER_CACHE or point it at a writable folder"),
]


def checks() -> list[dict[str, str | bool | None]]:
    """One row per environment and adapter check: stage, name, ok, problem, fix."""
    rows: list[dict[str, str | bool | None]] = []
    for name, check, fix in ENV_CHECKS:
        try:
            problem = check()
        except Exception as exc:  # a broken check is itself a problem worth showing
            problem = f"check raised {type(exc).__name__}: {exc}"
        rows.append(
            {
                "stage": "environment",
                "name": name,
                "ok": problem is None,
                "problem": problem,
                "fix": fix,
            }
        )
    for adapter, problem in adapter_doctor():
        rows.append(
            {
                "stage": adapter.stage,
                "name": adapter.name,
                "ok": problem is None,
                "problem": problem,
                "fix": adapter.fix,
            }
        )
    return rows


def report() -> int:
    rows = checks()
    width = max(len(str(r["name"])) for r in rows)
    failed = 0
    for row in rows:
        failed += not row["ok"]
        line = f"{'ok  ' if row['ok'] else 'FAIL'} {row['stage']:<18} {row['name']:<{width}}"
        if not row["ok"]:
            line += f"  {row['problem']}  -> {row['fix']}"
        print(line)
    print(f"\n{len(rows) - failed}/{len(rows)} checks passed, {failed} failed")
    return 0 if failed == 0 else 1
