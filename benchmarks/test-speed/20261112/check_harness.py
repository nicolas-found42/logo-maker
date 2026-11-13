"""Exercise the real pytest/xdist boundary, including a deliberately failing test.

Run from the repository: uv run --locked python benchmarks/test-speed/20261112/check_harness.py
The temporary suite records each executed identity and rejects duplicate execution.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CASES = [
    ("cold", ["-n", "3", "--dist", "worksteal", "--cache-clear"], False),
    ("warm", ["-n", "3", "--dist", "worksteal"], False),
    ("no-cache", ["-n", "3", "--dist", "worksteal", "-p", "no:cacheprovider"], False),
    ("load", ["-n", "3", "--dist", "load"], False),
    ("serial", ["-n", "0"], False),
    ("failure", ["-n", "3", "--dist", "worksteal"], True),
    ("one-test", ["-n", "3", "--dist", "worksteal"], False),
]


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix="logo-test-scheduling-") as directory:
        folder = Path(directory)
        shutil.copyfile(ROOT / "tests/conftest.py", folder / "conftest.py")
        (folder / "pytest.ini").write_text("[pytest]\nmarkers = omit: selection probe\n")
        (folder / "test_probe.py").write_text(
            "import os\nfrom pathlib import Path\nimport pytest\n"
            "@pytest.mark.parametrize('value', [*range(10), pytest.param(10, marks=pytest.mark.omit)])\n"
            "def test_identity(value):\n"
            "    seen = Path(os.environ['SCHEDULING_SEEN']) / str(value)\n"
            "    with seen.open('x') as handle:\n"
            "        handle.write(str(value))\n"
            "    if os.environ['SCHEDULING_FAULT'] == 'yes' and value == 5:\n"
            "        pytest.fail('deliberate scheduling failure')\n"
        )
        for name, options, fault in CASES:
            seen = folder / name
            seen.mkdir()
            target = "test_probe.py::test_identity[0]" if name == "one-test" else "test_probe.py"
            command = [sys.executable, "-m", "pytest", "-q", target, "-m", "not omit", *options]
            result = subprocess.run(
                command,
                cwd=folder,
                env={
                    **os.environ,
                    "SCHEDULING_SEEN": str(seen),
                    "SCHEDULING_FAULT": "yes" if fault else "no",
                },
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            executed = sorted(int(path.name) for path in seen.iterdir())
            expected = [0] if name == "one-test" else list(range(10))
            if executed != expected or result.returncode != int(fault):
                raise RuntimeError(
                    f"{name}: identities={executed}, exit={result.returncode}\n{result.stdout}\n{result.stderr}"
                )
            results.append(
                {
                    "case": name,
                    "options": options,
                    "executed": executed,
                    "exitstatus": result.returncode,
                }
            )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
