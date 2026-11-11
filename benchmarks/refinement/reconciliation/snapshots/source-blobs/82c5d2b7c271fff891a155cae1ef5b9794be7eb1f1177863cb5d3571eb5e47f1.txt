"""Lights and world inside bpy: catalog rigs become area lights, the HDRI spec
becomes the environment (or a flat background color when `none`).
"""

from __future__ import annotations


def apply_lighting(rig_params: dict, hdri_path: str | None, hdri_strength: float) -> None:
    """Place every rig light aimed at the origin; build the world background."""
    import bpy
    import mathutils

    for item in rig_params.get("lights", []):
        kind = item.get("type", "area")
        data = bpy.data.lights.new(
            item.get("name", "Light"), "AREA" if kind == "area" else kind.upper()
        )
        if kind == "area":
            data.energy = float(item.get("energy", item.get("power_w", 100.0)))
            data.size = float(item.get("size", 3.0))
        else:
            data.energy = float(item.get("energy", item.get("power_w", 100.0)))
        obj = bpy.data.objects.new(data.name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = tuple(item.get("location", item.get("position", (0, 0, 5))))
        target = tuple(item.get("target", (0, 0, 0)))
        obj.rotation_euler = (
            (mathutils.Vector(target) - mathutils.Vector(obj.location))
            .to_track_quat("-Z", "Y")
            .to_euler()
        )

    world = bpy.data.worlds.new("LogoWorld")
    world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    bg = nodes["Background"]
    if hdri_path:
        env = nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdri_path)
        links.new(env.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = hdri_strength
    else:
        bg.inputs["Color"].default_value = (0.97, 0.96, 0.94, 1.0)
        bg.inputs["Strength"].default_value = max(hdri_strength, 0.25)
    bpy.context.scene.world = world
