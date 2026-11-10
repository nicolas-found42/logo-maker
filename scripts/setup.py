#!/usr/bin/env python3
"""Install every tool logo-maker uses, then warm the Metal kernels. Safe to rerun.

Steps: Homebrew go + fontforge, `go install` primitive, `uv sync`, `npm ci` in js/, GPU kernel warm-up.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIMITIVE = "github.com/fogleman/primitive@latest"


def step(cmd: list[str], *, cwd: Path = ROOT, timeout: float | None = None) -> None:
    print(f"$ {shlex.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, timeout=timeout)


# canvas@2.11.2 (via trianglify) has no prebuilt binary for Node 24, so `npm ci` compiles it;
# these are its documented macOS build libraries (github.com/Automattic/node-canvas README).
CANVAS_BUILD_LIBS = (
    "pkgconf",
    "cairo",
    "pango",
    "libpng",
    "jpeg-turbo",
    "giflib",
    "librsvg",
    "pixman",
)


def main() -> int:
    if sys.platform != "darwin":
        print(
            "note: GPU rendering is verified on Apple-silicon macOS; other systems render on CPU."
        )
    try:
        if shutil.which("brew"):
            missing = [
                pkg
                for pkg, binary in (("go", "go"), ("fontforge", "fontforge"))
                if shutil.which(binary) is None
            ]
            installed = subprocess.run(
                ["brew", "list", "--formula"], capture_output=True, text=True, check=True
            ).stdout.split()
            missing += [pkg for pkg in CANVAS_BUILD_LIBS if pkg not in installed]
            if missing:
                step(["brew", "install", *missing])
        elif shutil.which("go") is None or shutil.which("fontforge") is None:
            print("install go and fontforge with your package manager, then rerun", file=sys.stderr)
            return 1
        step(["go", "install", PRIMITIVE])
        step(["uv", "sync", "--locked"])
        step(["npm", "ci", "--no-audit", "--no-fund"], cwd=ROOT / "js")
        # First Metal compile takes 1.5-5 min with no output; never interrupt it.
        step(["uv", "run", "--locked", "python", "scripts/warm_gpu.py"], timeout=900)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"setup stopped: {exc}", file=sys.stderr)
        return 1
    print("setup complete; run `just doctor`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
