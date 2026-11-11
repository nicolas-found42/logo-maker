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


def test_export_uses_verified_snapshot_when_live_final_changes(tmp_path, monkeypatch):
    from logo_maker import export

    concept, motif = _concept(tmp_path, _disc)
    original = (concept / "final.png").read_bytes()
    (concept / ".build").mkdir()
    (concept / ".build/final.sampling.json").write_text(
        json.dumps({"published": True, "delivered_sha256": hashlib.sha256(original).hexdigest()})
    )
    real_hash, real_hero = export._sha256, export._hero

    def replace_after_hash(path):
        digest = real_hash(path)
        if digest == hashlib.sha256(original).hexdigest():
            Image.new("RGBA", (1200, 900), (255, 0, 0, 255)).save(concept / "final.png")
        return digest

    class InspectedHero(Exception):
        pass

    def inspect_hero(*args, **kwargs):
        hero = real_hero(*args, **kwargs)
        assert Image.open(hero).convert("RGBA").getpixel((1000, 1000)) == (30, 74, 122, 255)
        assert (concept / "final.png").read_bytes() != original
        raise InspectedHero

    monkeypatch.setattr(export, "_sha256", replace_after_hash)
    monkeypatch.setattr(export, "_hero", inspect_hero)
    with pytest.raises(InspectedHero):
        export._export_all(
            concept, tmp_path / "out", name="Sample", palette=PALETTE, motif_svg=motif
        )


def test_stalled_sampling_provenance_read_keeps_prior_exports_within_deadline(tmp_path):
    import os
    import threading
    import time

    from logo_maker.sampling import Budget, SamplingLimit

    if os.name != "posix":
        pytest.skip("bounded workers target macOS/Linux")
    concept, motif = _concept(tmp_path, _disc)
    (concept / ".build").mkdir()
    source = concept / ".build/final.sampling.json"
    os.mkfifo(source)
    out = tmp_path / "exports"
    out.mkdir()
    (out / "prior.txt").write_text("last approved export")
    stop = threading.Event()

    def release_old_unbounded_call():
        descriptor = None
        try:
            while not stop.is_set():
                try:
                    descriptor = os.open(source, os.O_WRONLY | os.O_NONBLOCK)
                    break
                except OSError:
                    stop.wait(0.01)
            if descriptor is not None and not stop.wait(10):
                with contextlib.suppress(BrokenPipeError):
                    os.write(descriptor, b"{}")
        finally:
            if descriptor is not None:
                os.close(descriptor)

    releaser = threading.Thread(target=release_old_unbounded_call, daemon=True)
    releaser.start()
    started = time.monotonic()
    try:
        with pytest.raises(SamplingLimit, match="time_limit"):
            export_all(
                concept,
                out,
                name="Sample",
                palette=PALETTE,
                motif_svg=motif,
                budget=Budget(wall_seconds=6),
            )
        assert time.monotonic() - started < 9, "provenance read overran the wall budget"
        assert (out / "prior.txt").read_text() == "last approved export"
    finally:
        stop.set()
        releaser.join(timeout=1)


@pytest.mark.parametrize("failure", ["deadline", "inner_error", "denied_live"])
def test_export_deadline_stops_tool_and_its_detached_browser(tmp_path, monkeypatch, failure):
    """A browser launcher cleans its detached child only when it receives termination."""
    import os
    import signal
    import sys
    import time

    from logo_maker.sampling import Budget, SamplingLimit

    if os.name != "posix":
        pytest.skip("production process-session cleanup targets macOS/Linux")
    real_killpg = os.killpg

    def denied_signals(group, sig):
        if failure == "denied_live" or sig == 0:
            raise PermissionError("simulated signal denial")
        return real_killpg(group, sig)

    if failure in {"inner_error", "denied_live"}:
        monkeypatch.setattr(os, "killpg", denied_signals)
    concept, motif = _concept(tmp_path, _disc)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    heartbeat = tmp_path / "heartbeat"
    pids = tmp_path / "pids.json"
    child_code = (
        "import sys,time; from pathlib import Path; p=Path(sys.argv[1]); "
        "end=time.monotonic()+60\n"
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
        f"#!{sys.executable}\n" + (driver_code if failure == "inner_error" else launcher_code)
    )
    helper.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    out = tmp_path / "exports"
    out.mkdir()
    (out / "prior.txt").write_text("approved prior export")
    try:
        expected_error = ExportError if failure == "inner_error" else SamplingLimit
        with pytest.raises(
            expected_error, match="cleanup unconfirmed" if failure == "denied_live" else None
        ):
            export_all(
                concept,
                out,
                name="Sample",
                palette=PALETTE,
                motif_svg=motif,
                # Include cold imports/format setup on the slower hosted Mac before
                # the external-tool lifecycle this regression is intended to reach.
                budget=Budget(wall_seconds=20),
            )
        assert heartbeat.exists(), "did not reach external-tool/browser lifecycle"
        if failure != "denied_live":
            stamp = heartbeat.stat().st_mtime_ns
            time.sleep(0.2)
            assert heartbeat.stat().st_mtime_ns == stamp, (
                "browser still performs work after export deadline"
            )
        assert (out / "prior.txt").read_text() == "approved prior export"
    finally:
        if pids.exists():
            spawned = json.loads(pids.read_text())
            group = None
            with contextlib.suppress(ProcessLookupError):
                group = os.getpgid(spawned["tool"])
                real_killpg(group, signal.SIGTERM)
            for pid in spawned.values():
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGTERM)
            if group is not None:
                with contextlib.suppress(ChildProcessError):
                    os.waitpid(group, 0)


@pytest.mark.parametrize("replacement", ["unqualified", "missing"])
def test_pipeline_export_rejects_concurrent_qualification_replacement(
    tmp_path, monkeypatch, replacement
):
    from logo_maker import export, pipeline, render
    from logo_maker.paths import LogoDir

    logo = LogoDir(tmp_path / "logo")
    pipeline.new(logo, "Test")
    logo.brief.write_text(
        'name="Test"\nsummary="Test mark"\ntone=["calm"]\n[palette]\nprimary="#245846"\n[fonts]\ndisplay="Test font"\n'
    )
    folder = logo.concept("a|b|c")
    image = Image.new("RGBA", (1200, 900))
    _disc(ImageDraw.Draw(image))
    image.save(folder / "final.png")
    (folder / "motif.svg").write_text(MOTIF)
    (folder / ".build").mkdir()
    sidecar = folder / ".build/final.sampling.json"
    record: dict = {
        "published": True,
        "delivered_sha256": hashlib.sha256((folder / "final.png").read_bytes()).hexdigest(),
        "profile": {"state": "qualified"},
        "outcomes": {"sampling": "profile_baseline"},
    }
    sidecar.write_text(json.dumps(record))
    (logo.ideation / "winner.json").write_text('{"winner":"a|b|c"}')
    prior = logo.exports / "prior.txt"
    prior.write_text("approved prior exports")
    monkeypatch.setattr(render, "artifact_current", lambda *a, **kw: True)
    real_export = export.export_all

    def race_after_qualification(*args, **kwargs):
        if replacement == "missing":
            sidecar.unlink()
        else:
            record["profile"]["state"] = "profile_unqualified"
            sidecar.write_text(json.dumps(record))
        return real_export(*args, **kwargs)

    monkeypatch.setattr(export, "export_all", race_after_qualification)
    with pytest.raises(ExportError, match="qualified sampling snapshot"):
        pipeline.export(logo)
    assert prior.read_text() == "approved prior exports"
    assert {p.name for p in logo.exports.iterdir()} == {"prior.txt"}
