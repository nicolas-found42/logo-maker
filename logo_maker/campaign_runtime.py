"""The project-local Codex launcher shared by the campaign CLI and MCP."""

from __future__ import annotations

import ctypes
import fcntl
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
from contextlib import nullcontext
from importlib.metadata import version
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from logo_maker import owned_process
from logo_maker.paths import LogoDir
from logo_maker.sampling import Budget
from logo_maker.sampling_diagnostics import sha256

VERSION = "0.167.1"
RUNTIME_SHA256 = "c53dc201b016a2fe2b0613a1f1bd13615c8b676cdab4b53d9be8d539eed4d01c"
CODE_MODE_HOST_SHA256 = "8aeb65c47ad7860691eca84f95b1b577ef85d27b8a8c7b288b3f39b42207ba7a"
RUNTIME_DIR = ".codex/logo-maker-runtime"
RUNTIME_BUILD = f"{VERSION}-{RUNTIME_SHA256[:12]}"
GPU_ACTIONS = frozenset(
    {
        "preflight",
        "prototype",
        "preview",
        "render",
        "qualify",
        "deliver",
        "author",
        "check-construction",
    }
)
JEV_ACTIONS = frozenset({"review", "diagnose", "evaluate"})
WORKER_ACTIONS = GPU_ACTIONS | JEV_ACTIONS | {"fetch-photo", "flat-preview"}


def runtime_digest(binary: Path) -> str:
    digest = sha256(binary)
    if digest != RUNTIME_SHA256:
        raise ValueError(f"expected the verified Codex {VERSION} binary at {binary}")
    return digest


def install_runtime(project: Path, source: Path) -> Path:
    """Stage the verified build beside the project. The installed apps are separate."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("the Codex Metal runtime requires Apple Silicon macOS")
    runtime_digest(source)
    root = project.resolve() / RUNTIME_DIR
    target = root / RUNTIME_BUILD / "codex"
    if not root.resolve().is_relative_to(project.resolve()):
        raise ValueError("runtime directory must stay inside the project")
    root.mkdir(parents=True, exist_ok=True)
    if not target.resolve().is_relative_to(root):
        raise ValueError("runtime binary must stay inside its installation")
    if target.exists():
        runtime_digest(target)
    else:
        with TemporaryDirectory(prefix="install-", dir=root) as temporary:
            staged = Path(temporary) / RUNTIME_BUILD
            staged.mkdir()
            shutil.copy2(source, staged / "codex")
            runtime_digest(staged / "codex")
            staged.rename(target.parent)
    host_source = source.with_name("codex-code-mode-host")
    if host_source.is_file():
        if sha256(host_source) != CODE_MODE_HOST_SHA256:
            raise ValueError("the Codex code-mode host differs from the verified build")
        host_target = target.with_name(host_source.name)
        with TemporaryDirectory(prefix="host-", dir=target.parent) as temporary:
            staged = Path(temporary) / host_source.name
            shutil.copy2(host_source, staged)
            if sha256(staged) != CODE_MODE_HOST_SHA256:
                raise ValueError("the Codex code-mode host changed during installation")
            staged.replace(host_target)
    return target


def _installation(target: Path) -> tuple[Path, Path]:
    for project in (target, *target.parents):
        runtime = project / RUNTIME_DIR
        if runtime.is_dir():
            binary = runtime / RUNTIME_BUILD / "codex"
            if not binary.is_file():
                raise RuntimeError(f"Install the verified Codex runtime build {RUNTIME_BUILD}.")
            if not binary.resolve().is_relative_to(project):
                raise ValueError("installed Codex runtime must be within the project")
            runtime_digest(binary)
            return project, binary
    raise RuntimeError("Install the pinned project-local Codex Metal runtime before this action.")


def _arguments(binary: Path, project: Path, action: str, record: dict) -> list[str]:
    policy = "permissions.logo-maker"
    domain = "openrouter.ai" if action in JEV_ACTIONS else None
    if action == "fetch-photo":
        from logo_maker.campaign_references import source_domain

        domain = source_domain(record["url"])
    args = [
        str(binary),
        "sandbox",
        "-P",
        "logo-maker",
        "-C",
        str(project),
        "-c",
        f'{policy}.filesystem={{":root"="read",":workspace_roots"="write",'
        '"/Applications/Blender.app"="deny",'
        '"/opt/homebrew/Caskroom/blender"="deny"}',
        "-c",
        f"{policy}.network.enabled={str(domain is not None).lower()}",
    ]
    if domain:
        args.extend(
            [
                "-c",
                "features.network_proxy=true",
                "-c",
                f'{policy}.network.mode="full"',
                "-c",
                f"{policy}.network.enable_socks5=false",
                "-c",
                f'{policy}.network.domains={{"{domain}"="allow"}}',
            ]
        )
    elif action in GPU_ACTIONS:
        args.append("--allow-metal")
    return args


def dispatch(logo: LogoDir, action: str, *, concepts=None, note="", record=None) -> dict:
    """Launch expensive campaign work with verified sandbox policy and bounded cleanup."""
    from logo_maker import campaign, pipeline

    installed = Path(__file__).resolve().parents[1]
    if (installed / "install.json").is_file() and installed.parent.name == ".codex":
        project = installed.parent.parent
        if not logo.root.resolve().is_relative_to(project):
            raise ValueError(f"campaign target must be inside the installed project: {project}")
    online = action in JEV_ACTIONS
    if action not in WORKER_ACTIONS:
        return campaign.execute(logo, action, concepts=concepts, note=note, record=record)
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("Codex campaign execution requires Apple Silicon macOS.")
    project, binary = _installation(logo.root.resolve())
    # Codex protects .codex itself from workspace writes.
    scratch_root = project / ".logo-maker-work"
    if scratch_root.resolve() != scratch_root:
        raise ValueError("campaign scratch must be a local project directory")
    scratch_root.mkdir(exist_ok=True)
    with (
        TemporaryDirectory(prefix="campaign-", dir=scratch_root) as scratch,
        NamedTemporaryFile(dir="/private/tmp", prefix="logo-maker-boundary-") as outside,
        socket.socket() as listener,
    ):
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        env = {
            "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin",
            "HOME": scratch,
            "CODEX_HOME": scratch,
            "TMPDIR": scratch,
            "PYTHONDONTWRITEBYTECODE": "1",
            "BLENDER_USER_RESOURCES": scratch,
            "LOGO_MAKER_CACHE": str(scratch_root / "cache"),
            "XDG_CACHE_HOME": str(scratch_root / "cache"),
            "CYCLES_METAL_DISABLE_BINARY_ARCHIVES": "1",
            "LOGO_MAKER_CODEX_RUNTIME_SHA256": RUNTIME_SHA256,
        }
        if online and (key := os.environ.get("OPENROUTER_API_KEY")):
            env["OPENROUTER_API_KEY"] = key
        payload = {
            "logo": str(logo.root.resolve()),
            "action": action,
            "concepts": concepts,
            "note": note,
            "record": record,
            "project": str(project),
            "outside": outside.name,
            "port": listener.getsockname()[1],
            "scratch": scratch,
        }
        result = owned_process.run(
            [
                *_arguments(binary, project, action, record or {}),
                "--",
                sys.executable,
                "-I",
                "-m",
                "logo_maker.campaign_runtime",
            ],
            input_text=json.dumps(payload),
            budget=Budget(6 * 3600),
            label=f"sandboxed campaign {action}",
            env=env,
            cwd=project,
        )
    if result.returncode:
        raise RuntimeError(
            result.stderr.strip() or f"sandboxed campaign exited {result.returncode}"
        )
    response = json.loads(result.stdout.splitlines()[-1])
    if response["kind"] == "authoring_needed":
        raise pipeline.AuthoringNeeded(
            response["message"],
            [Path(file) for file in response["files"]],
            questions=response["questions"],
            details=response["details"],
        )
    return response["result"]


def _assert_denied(path: str) -> None:
    try:
        fd = os.open(path, os.O_WRONLY)
    except PermissionError:
        return
    os.close(fd)
    raise RuntimeError(f"Codex sandbox allowed write access to {path}")


def _policy(project: Path | None = None) -> None:
    """Check actual Seatbelt policy even when called from an internal entry point."""
    if os.environ.get("CODEX_SANDBOX") != "seatbelt":
        raise RuntimeError("Campaign work requires the enforced Codex Seatbelt launcher.")
    check = ctypes.CDLL(None).sandbox_check
    check.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int)
    check.restype = ctypes.c_int
    if project and any(
        check(os.getpid(), b"file-read-data", 1, ctypes.c_char_p(os.fsencode(path))) <= 0
        for path in (
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "/opt/homebrew/Caskroom/blender",
        )
    ):
        raise RuntimeError("the campaign worker must deny access to the installed Blender app")
    protected = [
        Path("/Applications/Blender.app/Contents/MacOS/Blender"),
        Path("/private/tmp"),
    ]
    if project:
        protected.append(project / ".git" / "HEAD")
    for path in protected:
        for operation in (b"file-write-data", b"file-write-create"):
            if check(os.getpid(), operation, 1, ctypes.c_char_p(os.fsencode(path))) <= 0:
                raise RuntimeError(f"Codex sandbox does not protect {path}")


def _verify_boundary(project: Path, outside: str, port: int, scratch: Path) -> None:
    _policy(project)
    with NamedTemporaryFile(dir=scratch) as probe:
        probe.write(b"workspace write")
        probe.flush()
    _assert_denied(outside)
    inert = scratch / "Blender"
    shutil.copyfile("/usr/bin/true", inert)
    inert.chmod(0o700)
    try:
        subprocess.run([str(inert)], check=True, timeout=5)
    except PermissionError:
        pass
    else:
        raise RuntimeError("Codex sandbox allowed the Blender executable name.")
    try:
        connection = socket.create_connection(("127.0.0.1", port), timeout=2)
    except PermissionError:
        pass
    else:
        connection.close()
        raise RuntimeError("Codex sandbox allowed a direct localhost connection.")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "logo_maker.campaign_runtime",
            "--deny-write",
            outside,
        ],
        check=True,
        timeout=10,
    )


def _render_probe(directory: Path) -> None:
    from logo_maker.blender.metal import require_metal_device

    _policy()
    require_metal_device()
    import bpy

    from logo_maker.blender.execution import render_verified
    from logo_maker.blender.settings import apply_cycles_gpu, apply_quality

    apply_cycles_gpu()
    apply_quality({"resolution": 64, "samples": 4})
    bpy.context.scene.render.film_transparent = True  # ty: ignore[missing-attribute]
    image = directory / "preflight.png"
    report = render_verified(image, directory / "preflight.json")
    if not _verified_probe(report, directory):
        raise RuntimeError("Metal preflight could not verify rendered pixels and GPU denoising.")


def _run_author(script: Path, arguments: list[str]) -> None:
    import runpy

    from logo_maker.blender.metal import require_metal_device

    _policy()
    require_metal_device()
    sys.argv = [str(script), *arguments]
    runpy.run_path(str(script), run_name="__main__")


def _verified_probe(report: dict, directory: Path) -> bool:
    return (
        report["status"] == "verified"
        and report["denoiser_effective"]["device_type"] == "Metal"
        and [d["type"] for d in report["devices"] if d["use"]] == ["METAL"]
        and report["resolution"] == [64, 64]
        and report["png_sha256"] == sha256(directory / "preflight.png")
        and report["log_sha256"] == sha256(directory / "preflight.log")
    )


def _preflight(scratch: Path, *, refresh: bool) -> dict:
    from logo_maker.blender.metal import require_metal_device
    from logo_maker.study_render import code_identity, digest

    require_metal_device()
    identity = digest(
        {
            "codex": RUNTIME_SHA256,
            "renderer": code_identity(),
            "launcher": sha256(Path(__file__)),
            "bpy": version("bpy"),
            "os": platform.platform(),
            "archives": os.environ["CYCLES_METAL_DISABLE_BINARY_ARCHIVES"],
        }
    )
    root = scratch.parent / "preflight-cache"
    root.mkdir(exist_ok=True)
    target = root / identity
    with (root / f"{identity}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _prove_gpu(scratch, target, refresh)


def _prove_gpu(scratch: Path, target: Path, refresh: bool) -> dict:
    if not refresh and target.is_dir():
        try:
            report = json.loads((target / "preflight.json").read_text())
            if _verified_probe(report, target):
                return report
        except (OSError, ValueError, KeyError, TypeError):
            pass
    probe = owned_process.run(
        [sys.executable, "-m", "logo_maker.campaign_runtime", "--render-probe", str(scratch)],
        budget=Budget(905),
        timeout=900,
        label="Metal preflight",
    )
    if probe.returncode:
        raise RuntimeError(f"Metal preflight failed: {probe.stderr.strip() or probe.stdout}")
    report = json.loads((scratch / "preflight.json").read_text())
    if not _verified_probe(report, scratch):
        raise RuntimeError("Metal preflight evidence changed after the probe.")
    target.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix=".probe-", dir=target.parent) as temporary:
        for name in ("preflight.png", "preflight.log", "preflight.json"):
            staged = Path(temporary) / name
            shutil.copyfile(scratch / name, staged)
            staged.replace(target / name)
    return report


def _main() -> None:
    payload = json.load(sys.stdin)
    signal.signal(signal.SIGTERM, _cancel)
    action = payload["action"]
    scratch = Path(payload["scratch"])
    _verify_boundary(Path(payload["project"]), payload["outside"], payload["port"], scratch)
    # The cold compiler and large control renders compete for the same project GPU.
    job_lock = (
        (scratch.parent / "native.lock").open("a") if action in GPU_ACTIONS else nullcontext()
    )
    with job_lock as lock:
        if lock is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        _execute_worker(payload, scratch)


def _execute_worker(payload: dict, scratch: Path) -> None:
    from logo_maker import campaign, pipeline

    action = payload["action"]
    proof = (
        _preflight(scratch, refresh=bool((payload["record"] or {}).get("refresh")))
        if action in GPU_ACTIONS
        else None
    )
    try:
        result = (
            {
                "sandbox": "seatbelt",
                "metal": "verified",
                "oidn": "Metal",
                "codex": VERSION,
                "codex_sha256": RUNTIME_SHA256,
                "execution": proof,
            }
            if action == "preflight"
            else campaign.execute(
                LogoDir(Path(payload["logo"])),
                action,
                concepts=payload["concepts"],
                note=payload["note"],
                record=payload["record"],
            )
        )
        response = {"kind": "result", "result": result}
    except pipeline.AuthoringNeeded as exc:
        response = {
            "kind": "authoring_needed",
            "message": str(exc).splitlines()[0],
            "files": exc.files,
            "questions": exc.questions,
            "details": exc.details,
        }
    print(json.dumps(response, default=str))


def _cancel(signum, frame) -> None:
    raise InterruptedError("Codex campaign worker was interrupted")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--deny-write"]:
        _assert_denied(sys.argv[2])
    elif sys.argv[1:2] == ["--render-probe"]:
        _render_probe(Path(sys.argv[2]))
    elif sys.argv[1:2] == ["--author"]:
        _run_author(Path(sys.argv[2]), sys.argv[3:])
    else:
        _main()
