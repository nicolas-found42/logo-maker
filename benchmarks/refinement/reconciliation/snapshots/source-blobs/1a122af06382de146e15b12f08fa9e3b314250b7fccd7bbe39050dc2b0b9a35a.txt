"""Subprocess helpers: every external tool runs through here so failures carry their stderr."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from logo_maker.paths import JS_DIR


class ToolError(RuntimeError):
    """An external tool failed, timed out, or is missing. The message names the fix when known."""


def require(binary: str, fix: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise ToolError(f"{binary} not found on PATH; fix: {fix}")
    return path


def run(
    cmd: list[str],
    *,
    timeout: float,
    cwd: Path | None = None,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ToolError(f"{cmd[0]} not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"{cmd[0]} timed out after {timeout:.0f}s: {' '.join(cmd)}") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-2000:]
        raise ToolError(f"{' '.join(cmd[:3])} exited {proc.returncode}: {tail}")
    return proc


def node(script: str, payload: dict[str, Any], *, timeout: float = 300) -> dict[str, Any]:
    """Run `js/<script>.mjs` with a JSON payload on stdin; the script prints one JSON object on stdout."""
    require("node", "brew install node@24")
    path = JS_DIR / f"{script}.mjs"
    if not path.exists():
        raise ToolError(f"missing node script {path}")
    if not (JS_DIR / "node_modules").exists():
        raise ToolError("js/node_modules missing; fix: just setup (runs npm ci in js/)")
    proc = run(["node", str(path)], timeout=timeout, cwd=JS_DIR, input_text=json.dumps(payload))
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        raise ToolError(f"{script}.mjs printed nothing; stderr: {proc.stderr.strip()[-800:]}")
    return json.loads(lines[-1])
