"""Verify the Codex launch denial with an inert executable named Blender."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from logo_maker.campaign_runtime import _arguments

CHILD = """
import errno, subprocess, sys
subprocess.run(['/usr/bin/true'], check=True)
for path in sys.argv[1:]:
    try:
        subprocess.run([path], check=True)
    except OSError as exc:
        if exc.errno not in (errno.EACCES, errno.EPERM):
            raise
    else:
        raise SystemExit('sandbox allowed Blender-named executable: ' + path)
print('Blender and blender execution denied; ordinary commands work')
"""


def verify(binary: Path, workspace: Path) -> str:
    """Check an actual exec denial without launching the installed application."""
    with TemporaryDirectory(prefix="blender-boundary-", dir=workspace) as temporary:
        root = Path(temporary)
        blocked = [root / name for name in ("Blender", "blender")]
        for target in blocked:
            shutil.copyfile("/usr/bin/true", target)
            target.chmod(0o700)
        for target in blocked:
            subprocess.run([str(target)], check=True)
        command = [
            *_arguments(binary, workspace, "flat-preview", {}),
            "--",
            sys.executable,
            "-I",
            "-c",
            CHILD,
            *map(str, blocked),
        ]
        result = subprocess.run(
            command,
            env={"PATH": "/usr/bin:/bin", "HOME": temporary, "CODEX_HOME": temporary},
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    print(verify(args.binary.resolve(), args.workspace.resolve()))
