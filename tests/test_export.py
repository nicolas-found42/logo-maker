"""Export set contract: exact sizes, ICO entries, a truthful manifest, and refusal of broken heroes."""

from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from logo_maker.export import AVATAR_SIZE, FAVICON_SIZES, HERO_SIZE, ExportError, export_all

PALETTE = {"primary": "#1E4A7A", "background": "#F8F6F1", "ink": "#16232E"}
MOTIF = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000">
<path d="M500 80 L880 820 L120 820 Z" fill="#1E4A7A"/>
</svg>
"""


def _concept(tmp_path: Path, draw) -> tuple[Path, Path]:
    concept = tmp_path / "concept"
    concept.mkdir()
    image = Image.new("RGBA", (1200, 900), (0, 0, 0, 0))
    draw(ImageDraw.Draw(image))
    image.save(concept / "final.png")
    motif = concept / "motif.svg"
    motif.write_text(MOTIF)
    return concept, motif


def _disc(d: ImageDraw.ImageDraw) -> None:
    d.ellipse((350, 200, 850, 700), fill=(30, 74, 122, 255))


def test_export_set_sizes_and_manifest(tmp_path: Path) -> None:
    concept, motif = _concept(tmp_path, _disc)
    out = tmp_path / "exports"
    manifest = export_all(concept, out, name="Sample Brand", palette=PALETTE, motif_svg=motif)

    hero = np.asarray(Image.open(manifest["hero-transparent"]).convert("RGBA"))
    assert hero.shape[:2] == (HERO_SIZE, HERO_SIZE)
    assert hero[0, 0, 3] == 0
    assert hero[HERO_SIZE // 2, HERO_SIZE // 2, 3] == 255

    for size in FAVICON_SIZES:
        assert Image.open(manifest[f"favicon-{size}"]).size == (size, size)
    ico = Image.open(manifest["favicon-ico"])
    assert {(16, 16), (32, 32), (48, 48)} <= set(ico.info["sizes"])

    avatar = Image.open(manifest["avatar-1024"]).convert("RGB")
    assert avatar.size == (AVATAR_SIZE, AVATAR_SIZE)
    paper = tuple(int(PALETTE["background"][i : i + 2], 16) for i in (1, 3, 5))
    px = np.asarray(avatar)
    assert tuple(px[0, 0]) == paper  # corners stay clear for circular crops
    assert tuple(px[AVATAR_SIZE // 2, AVATAR_SIZE // 2]) != paper

    for key in ("hero-paper", "mark-color", "mark-mono", "pwa-manifest", "contact-sheet"):
        assert manifest[key].is_file(), key
    assert "#1E4A7A" not in manifest["mark-mono"].read_text().upper()

    record = json.loads((out / "manifest.json").read_text())
    assert record["name"] == "Sample Brand"
    assert set(record["files"]) == set(manifest)
    for key, entry in record["files"].items():
        path = out / entry["path"]
        data = path.read_bytes()
        assert entry["bytes"] == len(data), key
        assert entry["sha256"] == hashlib.sha256(data).hexdigest(), key


@pytest.mark.parametrize(
    ("draw", "message"),
    [
        (lambda d: None, "fully transparent"),
        (lambda d: d.ellipse((-200, 200, 500, 900), fill=(30, 74, 122, 255)), "touches the frame"),
    ],
)
def test_broken_hero_refuses_to_export(tmp_path: Path, draw, message: str) -> None:
    concept, motif = _concept(tmp_path, draw)
    with pytest.raises(ExportError, match=message):
        export_all(concept, tmp_path / "exports", name="Sample", palette=PALETTE, motif_svg=motif)


def test_export_deadline_keeps_prior_exports(tmp_path):
    from logo_maker.sampling import Budget, SamplingLimit

    concept, motif = _concept(tmp_path, _disc)
    out = tmp_path / "exports"
    out.mkdir()
    (out / "prior.txt").write_text("last approved export")
    clock = [0.0]
    budget = Budget(wall_seconds=1, clock=lambda: clock[0])
    clock[0] = 2
    with pytest.raises(SamplingLimit, match="time_limit"):
        export_all(concept, out, name="Sample", palette=PALETTE, motif_svg=motif, budget=budget)
    assert (out / "prior.txt").read_text() == "last approved export"


@pytest.mark.parametrize("failure", ["deadline", "inner_error"])
def test_export_deadline_stops_tool_and_its_detached_browser(tmp_path, monkeypatch, failure):
    """A browser launcher cleans its detached child only when it receives termination."""
    import os
    import signal
    import sys
    import time

    from logo_maker.sampling import Budget, SamplingLimit

    if os.name != "posix":
        pytest.skip("production process-session cleanup targets macOS/Linux")
    concept, motif = _concept(tmp_path, _disc)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    heartbeat = tmp_path / "heartbeat"
    pids = tmp_path / "pids.json"
    child_code = (
        "import sys,time; from pathlib import Path; p=Path(sys.argv[1]); "
        "end=time.monotonic()+15\n"
        "while time.monotonic()<end:\n p.write_text('alive'); time.sleep(0.03)\n"
    )
    helper = bin_dir / "node"
    launcher_code = (
        "import json,os,signal,subprocess,sys,time\n"
        "from pathlib import Path\n"
        f"child=subprocess.Popen([sys.executable,'-c',{child_code!r},{str(heartbeat)!r}],start_new_session=True)\n"
        "def stop(*args):\n"
        " time.sleep(0.3)\n"
        " try: os.killpg(child.pid,signal.SIGKILL)\n"
        " except ProcessLookupError: pass\n"
        " child.wait(); sys.exit(143)\n"
        "signal.signal(signal.SIGTERM,stop)\n"
        f"Path({str(pids)!r}).write_text(json.dumps({{'tool':os.getpid(),'browser':child.pid}}))\n"
        "child.wait()\n"
    )
    launcher = tmp_path / "launcher.py"
    launcher.write_text(launcher_code)
    driver_code = (
        "import subprocess,sys,time\nfrom pathlib import Path\n"
        f"subprocess.Popen([sys.executable,{str(launcher)!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
        "end=time.monotonic()+2\n"
        f"while not Path({str(heartbeat)!r}).exists() and time.monotonic()<end: time.sleep(0.01)\n"
        "sys.exit(2)\n"
    )
    helper.write_text(
        f"#!{sys.executable}\n" + (launcher_code if failure == "deadline" else driver_code)
    )
    helper.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    out = tmp_path / "exports"
    out.mkdir()
    (out / "prior.txt").write_text("approved prior export")
    try:
        expected_error = SamplingLimit if failure == "deadline" else ExportError
        with pytest.raises(expected_error):
            export_all(
                concept,
                out,
                name="Sample",
                palette=PALETTE,
                motif_svg=motif,
                budget=Budget(wall_seconds=4),
            )
        assert heartbeat.exists(), "did not reach external-tool/browser lifecycle"
        stamp = heartbeat.stat().st_mtime_ns
        time.sleep(0.2)
        assert heartbeat.stat().st_mtime_ns == stamp, (
            "browser still performs work after export deadline"
        )
        assert (out / "prior.txt").read_text() == "approved prior export"
    finally:
        if pids.exists():
            spawned = json.loads(pids.read_text())
            for pid in spawned.values():
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGTERM)


@pytest.mark.parametrize("live", [False, True])
def test_export_cleanup_checks_permission_error_group_state(monkeypatch, live):
    """Darwin's zombie-only EPERM differs from denial while work is still running."""
    import os
    import signal
    import subprocess
    import sys
    import time

    from logo_maker.export import _stop_export_session
    from logo_maker.sampling import Budget, SamplingLimit

    if os.name != "posix":
        pytest.skip("POSIX export lifecycle")
    worker = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(15)" if live else "pass"],
        start_new_session=True,
    )
    try:
        if not live:
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                state = subprocess.check_output(
                    ["/bin/ps", "-p", str(worker.pid), "-o", "stat="], text=True
                ).strip()
                if state.startswith("Z"):
                    break
                time.sleep(0.01)
            assert state.startswith("Z"), "did not reach unreaped process state"

        def denied(*args):
            raise PermissionError("signal denied")

        monkeypatch.setattr(os, "killpg", denied)
        if live:
            with pytest.raises(SamplingLimit, match="cleanup unconfirmed"):
                _stop_export_session(worker, Budget(wall_seconds=2))
        else:
            _stop_export_session(worker, Budget(wall_seconds=2))
            assert worker.returncode == 0
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.kill(worker.pid, signal.SIGKILL)
        worker.wait()
