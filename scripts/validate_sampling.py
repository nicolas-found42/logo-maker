"""Repeatable M5 sampling qualification jobs through the real final/export path.

Use --prepare-baseline REV to extract an isolated read-only baseline source tree;
then --arm baseline/current --case matte/metal/glass --seed N --threshold X.
This produces evidence, never a qualified profile or an owner approval.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

WORKER = """
import json, time, sys
from pathlib import Path
from logo_maker import pipeline, render, export
started = time.monotonic()
folder = Path(sys.argv[1])
pipeline.prepare_motif(folder)
result = render.render(folder, "final")
paths = export.export_all(folder, folder / "exports", name="Sampling fixture",
    palette={"primary":"#245846", "background":"#F4F1EA", "ink":"#131D18"},
    motif_svg=folder / "motif.svg")
report = {"seconds":time.monotonic()-started, "render_seconds":result.seconds,
          "execution":str(result.execution), "png":str(result.png),
          "sampling":str(getattr(result,"sampling",None)),
          "export_manifest":str(folder / "exports/manifest.json"),
          "timing_scope":"host motif preparation, compile, process startup, all rendering/denoising/diagnostic IO, downsample and full export; excludes parent process launch and later review sheets",
          "kernel_cache_state":"unknown", "owner_review":"pending", "qualification":"incomplete"}
(folder / "measurement.json").write_text(json.dumps(report,indent=2)+"\\n")
print(json.dumps(report), flush=True)
"""


def fixture(folder: Path, case: str, seed: int, threshold: float | None, cap: int | None) -> None:
    folder.mkdir(parents=True, exist_ok=False)
    motif = (
        "M210 720 L500 180 L790 720 L655 720 L500 420 L345 720 Z"
        if case != "glass"
        else "M220 230 L470 230 L470 420 L780 420 L780 770 L530 770 L530 580 L220 580 Z"
    )
    (folder / "motif.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000">'
        f'<path id="symbol" fill="#245846" d="{motif}"/></svg>'
    )
    material = {
        "matte": "matte_plastic",
        "metal": "polished_metal",
        "glass": "clear_glass",
        "typography": "polished_metal",
    }[case]
    font = ROOT / "benchmarks/omp/recipe/OpenSans-Bold-static.ttf"
    render_fields = ""
    if threshold is not None:
        render_fields += f"adaptive_threshold = {threshold}\n"
    if cap is not None:
        render_fields += f"max_samples = {cap}\n"
    (folder / "scene.toml").write_text(f'''
[meta]
concept = "sampling-{case}|embossed_plate|{material}"
treatment = "embossed_plate"
seed = {seed}
[camera]
tilt_deg = 25
framing = 0.8
[lighting]
rig = "studio_soft"
hdri = "none"
hdri_strength = 0.25
[render]
renderer = "cycles"
{render_fields}
[sampling]
wall_seconds = 900
attempt_limit = 2
diagnostic_bytes = 2147483648
[materials.surface]
preset = "{material}"
color = "#245846"
[materials.dark]
preset = "matte_plastic"
color = "#0A1015"
[materials.type]
preset = "polished_metal"
color = "#C5CBCD"
[[components]]
kind = "plate"
material = "dark"
radius = 0.95
thickness = 0.1
bevel = 0.02
[[components]]
kind = "relief"
material = "surface"
height = 0.16
base = 0.1
[[components]]
kind = "ring_text"
material = "type"
text = "OPTICS • 08 BETA • OPTICS • 08 BETA • "
font = "{font}"
radius = 0.78
cap_height = 0.045
base = {0.172 if case == "typography" else 0.105}
''')
    (folder / "brief.json").write_text(
        json.dumps(
            {
                "purpose": "material/typography/alpha qualification fixture, not a design template",
                "brief": "Matte directional instrument mark"
                if case != "glass"
                else "Translucent interlocking optics mark",
                "material": case,
                "owner_review": "pending",
                "fine_type_cap_height_scene_units": 0.045,
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--prepare-baseline")
    parser.add_argument("--arm", choices=["baseline", "current"], default="current")
    parser.add_argument(
        "--case", choices=["matte", "metal", "glass", "typography"], default="matte"
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--cap", type=int)
    parser.add_argument("--run", default="1")
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    baseline = args.root / "baseline-source"
    if args.prepare_baseline:
        archive = args.root / "baseline.tar"
        with archive.open("wb") as stream:
            subprocess.run(
                ["git", "archive", args.prepare_baseline], cwd=ROOT, stdout=stream, check=True
            )
        baseline.mkdir(exist_ok=False)
        with tarfile.open(archive) as bundle:
            bundle.extractall(baseline, filter="data")
        archive.unlink()
        (baseline / "js/node_modules").symlink_to(
            ROOT / "js/node_modules", target_is_directory=True
        )
        (args.root / "baseline-revision.txt").write_text(args.prepare_baseline + "\n")
        return
    folder = (
        args.root
        / f"{args.case}-{args.arm}-seed{args.seed}-t{args.threshold or 0.01}-run{args.run}"
    )
    fixture(folder, args.case, args.seed, args.threshold, args.cap)
    cwd = baseline if args.arm == "baseline" else ROOT
    with (folder / "host.log").open("w") as log:
        proc = subprocess.run(
            [sys.executable, "-c", WORKER, str(folder.resolve())],
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=1000,
            check=False,
        )
    if proc.returncode:
        print((folder / "host.log").read_text()[-3000:])
        raise SystemExit(proc.returncode)
    print((folder / "measurement.json").read_text())


if __name__ == "__main__":
    main()
