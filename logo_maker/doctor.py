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
    if line is None:
        return f"bpy GPU probe failed: {(proc.stderr or proc.stdout).strip()[-300:]}"
    return None if line[6:] else "no Metal GPU device visible to Cycles (renders fall back to CPU)"


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
    out = subprocess.run(
        ["node", "--version"], capture_output=True, text=True, check=False
    ).stdout.strip()
    major = int(out.lstrip("v").split(".")[0]) if out.startswith("v") else 0
    return None if major >= 24 else f"node {out} is older than 24"


ENV_CHECKS: list[tuple[str, Callable[[], str | None], str]] = [
    ("jev API key", _jev_key, "export OPENROUTER_API_KEY=..."),
    ("Node.js >= 24", _node, "brew install node@24"),
    ("Cycles Metal GPU", _gpu, "update macOS / use an Apple-silicon Mac"),
    ("Metal kernel cache", _kernels, "just warm-gpu"),
]


def report() -> int:
    rows: list[tuple[str, str, str | None, str, bool]] = []
    for name, check, fix in ENV_CHECKS:
        rows.append(("environment", name, check(), fix, name != "Metal kernel cache"))
    for adapter, problem in adapter_doctor():
        rows.append((adapter.stage, adapter.name, problem, adapter.fix, adapter.required))
    width = max(len(r[1]) for r in rows)
    failed = warned = 0
    for stage, name, problem, fix, required in rows:
        mark = "ok  " if problem is None else ("FAIL" if required else "warn")
        failed += problem is not None and required
        warned += problem is not None and not required
        line = f"{mark} {stage:<18} {name:<{width}}"
        if problem:
            line += f"  {problem}  -> {fix}"
        print(line)
    print(
        f"\n{len(rows) - failed - warned}/{len(rows)} checks passed, {failed} failed, {warned} optional warnings"
    )
    return 0 if failed == 0 else 1
