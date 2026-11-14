"""Exercise the real sandbox using a sanitized, disposable Codex home."""

import os
import pathlib
import socket
import subprocess
import sys
import tempfile

workspace = pathlib.Path(__file__).resolve().parents[2]
scratch = pathlib.Path(__file__).resolve().parent
stock = os.environ.get("STOCK_CODEX", "/opt/homebrew/bin/codex")
candidate = sys.argv[1]
python = workspace / ".venv/bin/python"
env = {
    "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin",
    "HOME": str(scratch / "home"),
    "CODEX_HOME": str(scratch / "home"),
    "TMPDIR": str(scratch / "tmp"),
    "PYTHONDONTWRITEBYTECODE": "1",
    "LOGO_MAKER_CACHE": str(scratch / "cache"),
    "XDG_CACHE_HOME": str(scratch / "cache"),
    "BLENDER_USER_RESOURCES": str(scratch / "blender"),
    "CYCLES_METAL_DISABLE_BINARY_ARCHIVES": "1",
}
(scratch / "cache").mkdir(exist_ok=True)
opts = [
    "sandbox",
    "-P",
    "metal-trial",
    "-C",
    str(workspace),
    "-c",
    'permissions.metal-trial.filesystem={":root"="read",":workspace_roots"="write"}',
    "-c",
    "permissions.metal-trial.network.enabled=false",
]


def run(exe, flags, argv, *, returncode=0, substring=None, timeout=25):
    args = [exe, *opts, *flags, "--", *map(str, argv)]
    p = subprocess.run(
        args, cwd=workspace, env=env, text=True, capture_output=True, timeout=timeout
    )
    print(p.stdout, end="", flush=True)
    if p.returncode != returncode or (substring and substring not in p.stdout + p.stderr):
        print(p.stderr, end="", flush=True)
        raise SystemExit(
            f"unexpected result: {exe} flags {flags}; exit {p.returncode}, expected {returncode}"
        )


if len(sys.argv) == 3 and sys.argv[2] == "--blender":
    run(
        candidate,
        ["--allow-metal"],
        [
            python,
            "-c",
            "from logo_maker.doctor import _gpu; result = _gpu(); print(result or 'Cycles Metal GPU: OK'); raise SystemExit(result is not None)",
        ],
        substring="Cycles Metal GPU: OK",
        timeout=135,
    )
    run(
        candidate,
        ["--allow-metal"],
        [python, scratch / "cycles-probe.py"],
        substring="Verified Cycles Metal and OIDN Metal",
        timeout=900,
    )
    raise SystemExit(0)

probe = [scratch / "metal-probe", "--shared-event"]
run(stock, [], probe, returncode=10, substring="devices=0 default=<nil>")
run(candidate, [], probe, returncode=10, substring="devices=0 default=<nil>")
run(candidate, ["--allow-metal"], probe, substring="GPU shared event signaled value 42")
for profile in (
    ["sandbox", "-P", ":danger-full-access", "-C", str(workspace)],
    ["sandbox", "-P", ":workspace", "-C", str(workspace)],
    [
        *opts[:5],
        "-c",
        'permissions.metal-trial.filesystem={":root"="read",":workspace_roots"="write",":slash_tmp"="write"}',
        *opts[7:],
    ],
):
    p = subprocess.run(
        [candidate, *profile, "--allow-metal", "--", str(scratch / "metal-probe")],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        timeout=25,
    )
    if (
        p.returncode == 0
        or "devices=" in p.stdout
        or "--allow-metal requires an enforced profile" not in p.stderr
    ):
        raise SystemExit(f"unsafe profile guard was not reached: {p.returncode} {p.stderr}")
    print("profile refused:", p.stderr.strip().splitlines()[-1], flush=True)

with (
    tempfile.NamedTemporaryFile(dir="/private/tmp", prefix="metal-boundary-") as outside,
    socket.socket() as server,
):
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import socket,sys; socket.create_connection(('127.0.0.1',int(sys.argv[1])),2).close()",
            str(server.getsockname()[1]),
        ],
        check=True,
    )
    for exe, flag in ((stock, []), (candidate, ["--allow-metal"])):
        run(
            exe,
            flag,
            [
                python,
                "-I",
                scratch / "boundary.py",
                scratch,
                workspace / ".git",
                outside.name,
                server.getsockname()[1],
            ],
            substring="file write denied: installed Blender",
        )
print("Stock-versus-candidate regression and enforcement checks passed", flush=True)
