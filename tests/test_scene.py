"""Scene validation: every error names the field that caused it."""

from __future__ import annotations

import pytest

from logo_maker.scene import SceneError, from_treatment, load_scene

MINIMAL = """
[meta]
concept = "a|b|c"
treatment = "embossed_plate"
seed = 1

[materials.surface]
preset = "wax"

[[components]]
kind = "plate"
material = "surface"
"""


def write(tmp_path, text=MINIMAL):
    path = tmp_path / "scene.toml"
    path.write_text(text)
    return path


def test_minimal_validates(tmp_path):
    scene = load_scene(write(tmp_path))
    assert scene["meta"]["seed"] == 1
    assert scene["components"][0]["kind"] == "plate"
    assert scene["render"]["exposure"] == 0.0


def test_missing_concept_names_field(tmp_path):
    with pytest.raises(SceneError, match="concept"):
        load_scene(write(tmp_path, MINIMAL.replace('concept = "a|b|c"\n', "")))


def test_unknown_treatment(tmp_path):
    with pytest.raises(SceneError, match="treatment"):
        load_scene(write(tmp_path, MINIMAL.replace("embossed_plate", "molten_lava")))


def test_framing_out_of_range(tmp_path):
    with pytest.raises(SceneError, match="framing"):
        load_scene(write(tmp_path, MINIMAL + "\n[camera]\nframing = 1.4\n"))


def test_unknown_component_kind(tmp_path):
    with pytest.raises(SceneError, match="kind"):
        load_scene(write(tmp_path, MINIMAL.replace('kind = "plate"', 'kind = "teleporter"')))


def test_unknown_material_preset(tmp_path):
    with pytest.raises(SceneError, match="preset"):
        load_scene(write(tmp_path, MINIMAL.replace('preset = "wax"', 'preset = "unobtainium"')))


def test_unknown_lighting_rig(tmp_path):
    with pytest.raises(SceneError, match="rig"):
        load_scene(write(tmp_path, MINIMAL + '\n[lighting]\nrig = "candlelight"\n'))


def test_bad_renderer_and_look(tmp_path):
    with pytest.raises(SceneError, match="renderer"):
        load_scene(write(tmp_path, MINIMAL + '\n[render]\nrenderer = "pixar"\n'))
    with pytest.raises(SceneError, match="look"):
        load_scene(write(tmp_path, MINIMAL + '\n[render]\nlook = "anime"\n'))


def test_ring_text_needs_text_and_font(tmp_path):
    comp = '\n[[components]]\nkind = "ring_text"\nmaterial = "surface"\n'
    with pytest.raises(SceneError, match="text"):
        load_scene(write(tmp_path, MINIMAL + comp))


def test_mesh_needs_path(tmp_path):
    comp = '\n[[components]]\nkind = "mesh"\nmaterial = "surface"\n'
    with pytest.raises(SceneError, match="path"):
        load_scene(write(tmp_path, MINIMAL + comp))


def test_cad_plate_edge_relief_modes(tmp_path):
    comp = '\n[[components]]\nkind = "cad"\nmaterial = "surface"\nop = "lathe"\n'
    with pytest.raises(SceneError, match="cad"):
        load_scene(write(tmp_path, MINIMAL + comp))
    comp = '\n[[components]]\nkind = "relief"\nmaterial = "surface"\nmode = "carve"\n'
    with pytest.raises(SceneError, match="mode"):
        load_scene(write(tmp_path, MINIMAL + comp))
    comp = '\n[[components]]\nkind = "recess"\nmaterial = "surface"\ndepth = 0.05\n'
    with pytest.raises(SceneError, match="recess"):
        load_scene(write(tmp_path, MINIMAL + comp))


def test_from_treatment_rejects_unknowns():
    with pytest.raises(SceneError, match="treatment"):
        from_treatment("molten_lava", motif_json={}, palette={}, material_id="wax", seed=1)
    with pytest.raises(SceneError, match="material"):
        from_treatment("medallion", motif_json={}, palette={}, material_id="unobtainium", seed=1)


def test_from_treatment_emits_valid_toml(tmp_path):
    import tomllib

    text = from_treatment(
        "medallion",
        motif_json={},
        palette={"primary": "#112233"},
        material_id="polished_metal",
        seed=42,
    )
    parsed = tomllib.loads(text)
    assert parsed["meta"]["seed"] == 42
    assert parsed["materials"]["surface"]["color"] == "#112233"
    assert any(c["kind"] == "ring_text" for c in parsed["components"])


def test_sampling_overrides_preserve_false_zero_and_explicit_seed(tmp_path):
    from logo_maker import scene as scene_mod

    text = (
        MINIMAL
        + """
[render]
adaptive = false
adaptive_threshold = 0.0
min_samples = 0
max_samples = 128
seed = 99
[sampling]
wall_seconds = 120
attempt_limit = 1
"""
    )
    path = write(tmp_path, text)
    scene = load_scene(path)
    quality = scene_mod.sampling_quality(scene, "final")
    assert quality["adaptive"] is False
    assert quality["adaptive_threshold"] == 0
    assert quality["seed"] == 99
    assert quality["samples"] == 128
    assert quality["overrides"] == {
        "adaptive": False,
        "adaptive_threshold": 0.0,
        "min_samples": 0,
        "max_samples": 128,
        "seed": 99,
    }
    assert scene["sampling"]["attempt_limit"] == 1


def test_authored_mesh_shading_preserves_explicit_flat_faces(tmp_path):
    path = tmp_path / "scene.toml"
    path.write_text(
        MINIMAL.replace('kind = "plate"', 'kind = "mesh"\npath = "fold.ply"\nsmooth=false')
    )
    assert load_scene(path)["components"][0]["smooth"] is False
    path.write_text(path.read_text().replace("smooth=false", 'smooth="false"'))
    with pytest.raises(SceneError, match="smooth must be a boolean"):
        load_scene(path)


@pytest.mark.parametrize("vector", ["[0,0,0]", "[1,0]", '[1,"x",0]', "[nan,0,0]"])
def test_material_tangent_requires_finite_nonzero_direction(tmp_path, vector):
    path = tmp_path / "scene.toml"
    text = MINIMAL.replace('preset = "wax"', 'preset = "brushed_metal"\ntangent = [1,0,0]')
    path.write_text(text)
    assert load_scene(path)["materials"]["surface"]["tangent"] == [1, 0, 0]
    path.write_text(text.replace("[1,0,0]", vector))
    with pytest.raises(SceneError, match="tangent must be"):
        load_scene(path)


def test_compilation_forwards_authored_brushing_direction(tmp_path):
    import json

    from logo_maker.scene import compile

    text = MINIMAL.replace('preset = "wax"', 'preset = "brushed_metal"\ntangent = [1,0,0]')
    (tmp_path / "scene.toml").write_text(text + '\n[lighting]\nhdri="none"\n')
    (tmp_path / "motif.json").write_text('{"viewbox":1000,"layers":[]}')
    compiled = json.loads(compile(tmp_path, "preview").read_text())
    assert compiled["materials"]["surface"]["tangent"] == [1, 0, 0]


def test_compilation_forwards_authored_exposure_to_native_render(tmp_path):
    import json

    from logo_maker.scene import compile

    write(tmp_path, MINIMAL + '\n[render]\nexposure = -1.5\n[lighting]\nhdri = "none"\n')
    (tmp_path / "motif.json").write_text('{"viewbox":1000,"layers":[]}')
    compiled = json.loads(compile(tmp_path, "preview").read_text())
    assert compiled["render"]["exposure"] == -1.5
    assert compiled["quality"]["exposure"] == -1.5


@pytest.mark.parametrize("value", ["nan", "inf", "-33", "33", "true", '"dark"'])
def test_exposure_rejects_invalid_values(tmp_path, value):
    with pytest.raises(SceneError, match="exposure"):
        load_scene(write(tmp_path, MINIMAL + f"\n[render]\nexposure = {value}\n"))


@pytest.mark.parametrize("renderer", ["mitsuba", "luxcore", "three"])
def test_other_backends_reject_exposure_they_cannot_honor(tmp_path, renderer):
    text = MINIMAL + f'\n[render]\nrenderer = "{renderer}"\nexposure = -1.5\n'
    with pytest.raises(SceneError, match=r"exposure.*only for cycles"):
        load_scene(write(tmp_path, text))
