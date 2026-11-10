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
