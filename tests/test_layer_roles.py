"""Layer-aware treatment output: per-role materials and split mark components."""

import json
import tomllib
from pathlib import Path

from logo_maker import scene as scene_mod
from logo_maker.scene import SceneError, from_treatment, load_scene


def _motif() -> dict:
    def circle(cx, cy, r, n=24):
        import math

        return [
            [cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)]
            for i in range(n)
        ]

    return {
        "viewbox": 1000,
        "layers": [
            {
                "id": "disc",
                "role": "primary",
                "fill": "#224466",
                "height": 1.0,
                "contours": [circle(500, 500, 400)],
            },
            {
                "id": "bar",
                "role": "accent",
                "fill": "#DDAA33",
                "height": 2.0,
                "contours": [[[300, 450], [700, 450], [700, 550], [300, 550]]],
            },
            {
                "id": "ghost",
                "role": "secondary",
                "fill": "#889988",
                "height": 0.0,
                "contours": [[[100, 100], [200, 100], [200, 200], [100, 200]]],
            },
        ],
    }


def test_roles_split_materials_and_components(tmp_path: Path):
    text = from_treatment(
        "extruded_solid",
        motif_json=_motif(),
        palette={"primary": "#224466", "background": "#F2EFE9"},
        material_id="porcelain",
        seed=3,
    )
    data = tomllib.loads(text)
    assert set(data["materials"]) == {"surface", "primary", "accent"}
    assert data["materials"]["surface"]["color"] == "#F2EFE9"
    assert data["materials"]["accent"]["color"] == "#DDAA33"
    assert data["materials"]["primary"]["color"] == "#224466"
    comps = data["components"]
    assert len(comps) == 2  # one extrude per live role; height-0 ghost skipped
    by_role = {c["material"]: c for c in comps}
    assert by_role["accent"]["layers"] == ["bar"]
    assert by_role["accent"]["depth"] == 0.22 * 2.0
    assert by_role["primary"]["layers"] == ["disc"]
    assert by_role["primary"]["depth"] == 0.22


def test_emitted_scene_loads_and_compiles_scaled(tmp_path: Path):
    text = from_treatment(
        "embossed_plate",
        motif_json=_motif(),
        palette={"primary": "#224466"},
        material_id="porcelain",
        seed=3,
    )
    text = text.replace('hdri = "polyhaven:poly_haven_studio"', 'hdri = "none"')  # stay offline
    concept = tmp_path / "c"
    concept.mkdir()
    (concept / "motif.json").write_text(json.dumps(_motif()))
    (concept / "scene.toml").write_text(text)
    scene = load_scene(concept / "scene.toml")
    reliefs = [c for c in scene["components"] if c["kind"] == "relief"]
    assert {c["material"] for c in reliefs} == {"primary", "accent"}
    out = scene_mod.compile(concept, "test")
    built = json.loads(out.read_text())
    tops = {}
    for obj in built["objects"]:
        if obj["kind"] != "relief":
            continue
        import trimesh

        mesh = trimesh.load(concept / ".build" / obj["mesh"])
        tops[obj["material"]] = round(float(mesh.bounds[1][2]), 4)
    assert tops["accent"] > tops["primary"]  # height 2.0 stands proud of 1.0


def _relief_width(tmp_path: Path, scale: float) -> float:
    import trimesh

    concept = tmp_path / f"s{scale}"
    concept.mkdir()
    (concept / "motif.json").write_text(json.dumps(_motif()))
    (concept / "scene.toml").write_text(
        '[meta]\nconcept = "x"\ntreatment = "embossed_plate"\nseed = 1\n'
        f"[mark]\nscale = {scale}\n"
        '[materials.surface]\npreset = "porcelain"\n'
        '[[components]]\nkind = "plate"\nmaterial = "surface"\n'
        '[[components]]\nkind = "relief"\nmaterial = "surface"\nlayers = [ "disc" ]\nheight = 0.05\n'
    )
    built = json.loads(scene_mod.compile(concept, "test").read_text())
    relief = next(o for o in built["objects"] if o["kind"] == "relief")
    plate = next(o for o in built["objects"] if o["kind"] == "plate")
    bounds = trimesh.load(concept / ".build" / relief["mesh"]).bounds
    plate_bounds = trimesh.load(concept / ".build" / plate["mesh"]).bounds
    assert plate_bounds[1][0] - plate_bounds[0][0] == __import__("pytest").approx(2.0, rel=0.02)
    center = (bounds[0][:2] + bounds[1][:2]) / 2
    assert abs(center).max() < 0.02  # scaled about the plate center
    return float(bounds[1][0] - bounds[0][0])


def test_mark_scale_resizes_mark_not_plate(tmp_path: Path):
    import pytest

    full = _relief_width(tmp_path, 1.0)
    assert full == pytest.approx(1.6, rel=0.02)  # r=400 of 1000 -> 0.8 units
    assert _relief_width(tmp_path, 0.5) == pytest.approx(full * 0.5, rel=0.02)
    for bad in (0.05, 2.5):
        (tmp_path / "bad.toml").write_text(
            f'[meta]\nconcept = "x"\ntreatment = "embossed_plate"\nseed = 1\n[mark]\nscale = {bad}\n'
            '[materials.surface]\npreset = "porcelain"\n'
            '[[components]]\nkind = "plate"\nmaterial = "surface"\n'
        )
        with pytest.raises(SceneError, match="mark"):
            load_scene(tmp_path / "bad.toml")


def test_height_scale_qa_knob(tmp_path: Path):
    concept = tmp_path / "c"
    concept.mkdir()
    (concept / "motif.json").write_text(json.dumps(_motif()))
    (concept / "scene.toml").write_text(
        '[meta]\nconcept = "x"\ntreatment = "embossed_plate"\nseed = 1\n'
        '[camera]\n[lighting]\nrig = "raking"\n'
        "[render]\nmax_samples = 128\nadaptive_threshold = 0.02\nalpha_cleanup = true\n"
        '[materials.surface]\npreset = "porcelain"\n'
        '[[components]]\nkind = "relief"\nmaterial = "surface"\n'
        'layers = [ "disc" ]\nheight = 0.1\nheight_scale = 1.4\n'
    )
    scene = load_scene(concept / "scene.toml")
    assert scene["render"]["max_samples"] == 128
    assert scene["render"]["adaptive_threshold"] == 0.02
    assert scene["render"]["alpha_cleanup"] is True
    out = scene_mod.compile(concept, "test")
    built = json.loads(out.read_text())
    assert built["quality"]["samples"] == 128
    assert built["quality"]["adaptive"] is True
    import trimesh

    mesh = trimesh.load(concept / ".build" / built["objects"][0]["mesh"])
    assert float(mesh.bounds[1][2] - mesh.bounds[0][2]) == __import__("pytest").approx(0.1 * 1.4)


def test_alpha_cleanup_clears_haze_and_keeps_edges(tmp_path: Path):
    import numpy as np
    from PIL import Image

    from logo_maker import checks
    from logo_maker.render import _alpha_cleanup_png

    arr = np.zeros((200, 200, 4), dtype=np.uint8)
    arr[..., 3] = 6  # haze veiling the whole background
    arr[60:140, 60:140] = (200, 100, 50, 255)
    arr[59, 60:140] = (200, 100, 50, 120)  # anti-aliased edge
    arr[50, 60:140, 3] = 12  # faint shadow inside the halo zone
    png = tmp_path / "t.png"
    Image.fromarray(arr).save(png)
    assert checks.alpha_report(png)["veil"]

    _alpha_cleanup_png(png)

    out = np.array(Image.open(png))
    assert out[5, 5, 3] == 0  # open-background haze cleared
    assert out[59, 100, 3] == 120  # edge gradient kept
    assert out[100, 100, 3] == 255  # body kept
    assert not checks.alpha_report(png)["veil"]
