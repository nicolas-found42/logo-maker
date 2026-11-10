"""Catalog completeness: every treatment/material/lighting id carries the params
the builder needs, so a preset can never compile into a missing field.
"""

from __future__ import annotations

from logo_maker.catalog import lighting, materials, treatments
from logo_maker.scene import COMPONENT_KINDS, SceneError, from_treatment

MATERIAL_NUMBERS = (
    "metallic",
    "roughness",
    "coat",
    "transmission",
    "emission_strength",
    "bump",
    "bump_scale",
)


def test_twelve_treatments_with_components():
    assert len(treatments()) == 12
    for entry in treatments().values():
        assert entry.description
        comps = entry.params.get("components")
        assert comps, f"{entry.id} has no starting components"
        for comp in comps:
            assert comp["kind"] in COMPONENT_KINDS, f"{entry.id}: {comp['kind']}"
            assert comp.get("material"), f"{entry.id}: component without material"


def test_every_treatment_emits_a_scene(tmp_path):
    import tomllib

    for treatment_id in treatments():
        text = from_treatment(treatment_id, motif_json={}, palette={}, material_id="clay", seed=7)
        parsed = tomllib.loads(text)  # must be valid TOML
        assert parsed["components"], treatment_id


def test_nineteen_materials_with_params():
    assert len(materials()) == 19
    for entry in materials().values():
        assert entry.description
        for key in MATERIAL_NUMBERS:
            assert key in entry.params, f"{entry.id} missing {key}"
            assert isinstance(entry.params[key], (int, float)), entry.id
        assert 0.0 <= entry.params["roughness"] <= 1.0, entry.id


def test_lighting_rigs():
    assert len(lighting()) >= 4
    for entry in lighting().values():
        assert entry.description
        lights = entry.params.get("lights")
        assert lights, f"{entry.id} has no lights"
        for light in lights:
            assert light["type"] in ("area", "point", "sun"), entry.id
            assert len(light["location"]) == 3, entry.id
            assert light["energy"] > 0, entry.id


def test_unknown_treatment_and_material_raise():
    try:
        from_treatment("nope", motif_json={}, palette={}, material_id="wax", seed=1)
    except SceneError:
        pass
    else:
        raise AssertionError("expected SceneError")
