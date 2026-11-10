"""Materials inside bpy: Principled BSDF from resolved scene params, procedural
texture recipes from the catalog, and toon/clay variants for non-photoreal looks.
"""

from __future__ import annotations


def make_material(name: str, spec: dict, look: str = "photoreal"):
    """Create a Blender material for one resolved material spec."""
    import bpy

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    if look == "toon":
        _build_toon(mat, spec)
    elif look == "lineart":
        _build_clay(mat, spec)
    else:
        _build_principled(mat, spec)
    return mat


def _output(mat):
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    return nt, out


def _build_principled(mat, spec) -> None:

    nt, out = _output(mat)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.location = (0, 0)
    b.inputs["Base Color"].default_value = tuple(spec["base_color_linear"])
    b.inputs["Metallic"].default_value = spec["metallic"]
    b.inputs["Roughness"].default_value = spec["roughness"]
    for key, sock in (
        ("coat", "Coat Weight"),
        ("coat_roughness", "Coat Roughness"),
        ("subsurface", "Subsurface Weight"),
        ("sheen", "Sheen Weight"),
        ("transmission", "Transmission Weight"),
        ("ior", "IOR"),
        ("anisotropy", "Anisotropic"),
    ):
        if sock in b.inputs:
            b.inputs[sock].default_value = spec.get(key, b.inputs[sock].default_value)
    emission_strength = spec.get("emission_strength", 0.0)
    if emission_strength > 0:
        if "Emission Color" in b.inputs:
            b.inputs["Emission Color"].default_value = tuple(spec["emission_linear"])
        if "Emission Strength" in b.inputs:
            b.inputs["Emission Strength"].default_value = emission_strength
    _apply_texture(nt, b, spec)
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])


def _tex_coord(nt, scale: float):
    tex = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tex.outputs["Object"], mapping.inputs["Vector"])
    return mapping.outputs["Vector"]


def _out(node, *names):
    """First present output socket; Blender 5 renamed Fac to Factor and hides feature-specific sockets."""
    for name in names:
        socket = node.outputs.get(name)
        if socket is not None and socket.enabled:
            return socket
    return None


def _apply_texture(nt, principled, spec) -> None:
    recipe = spec.get("texture", "none")
    bump = spec.get("bump", 0.0)
    scale = spec.get("bump_scale", 40.0)
    if recipe == "none" and not bump:
        return
    coord = _tex_coord(nt, scale / 10.0)
    color_out, fac_out = None, None
    if recipe == "wood":
        wave = nt.nodes.new("ShaderNodeTexWave")
        wave.wave_type = "BANDS"
        wave.inputs["Scale"].default_value = 2.5
        wave.inputs["Distortion"].default_value = 3.0
        nt.links.new(coord, wave.inputs["Vector"])
        color_out, fac_out = _out(wave, "Color"), _out(wave, "Factor", "Fac")
    elif recipe == "stone":
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.feature = "SMOOTH_F1"
        vor.inputs["Scale"].default_value = 8.0
        nt.links.new(coord, vor.inputs["Vector"])
        color_out, fac_out = _out(vor, "Color"), _out(vor, "Distance")
    elif recipe == "brushed":
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 300.0
        noise.inputs["Detail"].default_value = 2.0
        stretch = nt.nodes.new("ShaderNodeMapping")
        stretch.inputs["Scale"].default_value = (1.0, 40.0, 1.0)
        nt.links.new(coord, stretch.inputs["Vector"])
        nt.links.new(stretch.outputs["Vector"], noise.inputs["Vector"])
        color_out, fac_out = None, _out(noise, "Factor", "Fac")
    elif recipe in ("fibers", "pores"):
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.feature = "DISTANCE_TO_EDGE" if recipe == "pores" else "N_SPHERE_RADIUS"
        vor.inputs["Scale"].default_value = 60.0 if recipe == "pores" else 120.0
        nt.links.new(coord, vor.inputs["Vector"])
        color_out, fac_out = None, _out(vor, "Distance", "Radius")
    else:  # noise_bump and anything unknown: fine surface variation
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = max(scale, 1.0)
        noise.inputs["Detail"].default_value = 6.0
        nt.links.new(coord, noise.inputs["Vector"])
        color_out, fac_out = None, _out(noise, "Factor", "Fac")
    if fac_out is not None and bump:
        bn = nt.nodes.new("ShaderNodeBump")
        bn.inputs["Strength"].default_value = bump
        nt.links.new(fac_out, bn.inputs["Height"])
        nt.links.new(bn.outputs["Normal"], principled.inputs["Normal"])
    if color_out is not None and recipe in ("wood", "stone"):
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["Factor"].default_value = 0.35
        mix.inputs["A"].default_value = tuple(principled.inputs["Base Color"].default_value)
        nt.links.new(color_out, mix.inputs["B"])
        nt.links.new(mix.outputs["Result"], principled.inputs["Base Color"])


def _build_toon(mat, spec) -> None:
    """Diffuse -> ShaderToRGB -> stepped ramp -> output, for the cel look."""
    nt, out = _output(mat)
    diffuse = nt.nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Color"].default_value = tuple(spec["base_color_linear"])
    diffuse.inputs["Roughness"].default_value = 1.0
    rgb = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    stops = ramp.color_ramp.elements
    stops[0].position, stops[0].color = 0.35, (0.25, 0.25, 0.25, 1.0)
    stops[1].position, stops[1].color = 0.65, (1.0, 1.0, 1.0, 1.0)
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(diffuse.outputs["BSDF"], rgb.inputs["Shader"])
    nt.links.new(rgb.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emit.inputs["Color"])
    if spec.get("emission_strength", 0.0) > 0:
        emit.inputs["Strength"].default_value = spec["emission_strength"]
        nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    else:
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(diffuse.outputs["BSDF"], mix.inputs[1])
        nt.links.new(emit.outputs["Emission"], mix.inputs[2])
        mix.inputs["Fac"].default_value = 0.85
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])


def _build_clay(mat, spec) -> None:
    """Flat light-grey diffuse: line art reads the outlines, not the shading."""
    nt, out = _output(mat)
    diffuse = nt.nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1.0)
    nt.links.new(diffuse.outputs["BSDF"], out.inputs["Surface"])
