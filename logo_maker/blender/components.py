"""Scene assembly inside bpy: import the host-built PLYs, assign materials, run
agent `bpy` components, drape cloth ribbons, and set up outline rendering.
"""

from __future__ import annotations

from pathlib import Path


def build_objects(scene: dict, build_dir: Path, materials: dict) -> list:
    """Import every compiled object; returns the render-visible Blender objects."""
    import bpy

    visible = []
    for obj in scene["objects"]:
        if obj["kind"] == "bpy":
            visible.extend(_run_agent_build(obj, scene, build_dir, materials))
            continue
        if obj["mesh"] is None:
            continue
        mesh_path = build_dir / obj["mesh"]
        bpy.ops.wm.ply_import(filepath=str(mesh_path))
        imported = bpy.context.selected_objects
        if not imported:
            raise RuntimeError(f"PLY import produced no object: {mesh_path}")
        bl_obj = imported[0]
        bl_obj.name = obj["name"]
        for poly in bl_obj.data.polygons:
            poly.use_smooth = True
        mat = materials.get(obj["material"])
        if mat is not None:
            bl_obj.data.materials.append(mat)
        params = obj.get("params", {})
        if params.get("bevel"):
            mod = bl_obj.modifiers.new("edge", "BEVEL")
            mod.width = float(params["bevel"])
            mod.segments = 3
            mod.limit_method = "ANGLE"
        if obj["kind"] == "ribbon" and params.get("drape"):
            _drape_ribbon(bl_obj, scene)
        visible.append(bl_obj)
    return visible


def _run_agent_build(obj: dict, scene: dict, build_dir: Path, materials: dict) -> list:
    """Execute the agent's `scene.py build(ctx)` fallback inside the concept folder."""
    from types import SimpleNamespace

    import bpy

    params = obj.get("params", {})
    concept_dir = build_dir.parent
    module_path = concept_dir / f"{params.get('module', 'scene')}.py"
    if not module_path.exists():
        raise RuntimeError(f"bpy component needs {module_path}, which does not exist")
    namespace: dict = {}
    # Deliberate escape hatch: run the agent-written scene.py build(ctx) in-concept.
    exec(compile(module_path.read_text(), str(module_path), "exec"), namespace)  # noqa: S102
    build = namespace.get(params.get("function", "build"))
    if not callable(build):
        raise RuntimeError(f"{module_path} defines no {params.get('function', 'build')} function")
    before = set(bpy.context.collection.objects)
    ctx = SimpleNamespace(
        materials=materials,
        scene=bpy.context.scene,
        link=lambda o: bpy.context.collection.objects.link(o),
    )
    build(ctx)
    return [o for o in bpy.context.collection.objects if o not in before]


def _drape_ribbon(bl_obj, scene: dict) -> None:
    """Drop the ribbon onto the plate with the cloth simulator; keep the analytic
    wave when the sim cannot run headless."""
    import bpy

    try:
        floor_z = next(
            (o["params"].get("top", 0.17) for o in scene["objects"] if o["kind"] == "plate"), 0.17
        )
        bpy.ops.mesh.primitive_plane_add(size=6.0, location=(0, 0, floor_z))
        floor = bpy.context.active_object
        floor.modifiers.new("collide", "COLLISION")
        floor.hide_render = True
        cloth = bl_obj.modifiers.new("cloth", "CLOTH")
        cloth.settings.quality = 5
        cloth.settings.mass = 0.3
        cloth.settings.bending_model = "LINEAR"
        start = bpy.context.scene.frame_current
        for frame in range(start + 1, start + 41):
            bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.objects.active = bl_obj
        bpy.ops.object.modifier_apply(modifier="cloth")
        bpy.data.objects.remove(floor, do_unlink=True)
        bpy.context.scene.frame_set(start)
    except Exception as exc:
        print(f"cloth drape failed ({exc}); keeping the analytic wave")


def setup_outlines(look: str, visible: list) -> None:
    """Crisp outlines for non-photoreal looks: exactly one line system each.

    Toon uses Freestyle (predictable pixel thickness on the CPU-friendly path);
    lineart uses the Line Art modifier alone. Mixing both double-draws strokes.
    """
    if look not in ("toon", "lineart"):
        return
    import bpy

    if look == "lineart":
        try:
            bpy.ops.object.grease_pencil_add(type="STROKE", location=(0, 0, 0))
            gp = bpy.context.active_object
            gp.name = "Outlines"
            mod = gp.modifiers.new("lines", "GREASE_PENCIL_LINEART")
            mod.source_type = "COLLECTION"
            mod.source_collection = bpy.context.collection
            mod.use_custom_camera = False
            if hasattr(mod, "thickness"):
                mod.thickness = 3
            return
        except Exception as exc:
            print(f"Line Art unavailable ({exc}); using Freestyle")
    bpy.context.scene.render.use_freestyle = True
    lineset = bpy.context.scene.view_layers[0].freestyle_settings.linesets.new("LogoLines")
    lineset.select_silhouette = True
    lineset.select_border = True
    lineset.select_crease = True
    if hasattr(lineset, "linestyle") and hasattr(lineset.linestyle, "thickness"):
        lineset.linestyle.thickness = 2.0


def setup_compositor(glare: float, dof_fstop: float) -> None:
    """Glare mix and camera depth of field. Headless pip bpy 5.2.3 exposes no
    Scene.node_tree, so glare degrades to a loud warning instead of a crash."""
    import bpy

    sc = bpy.context.scene
    if glare:
        try:
            nodes, links = sc.node_tree.nodes, sc.node_tree.links
        except AttributeError:
            print("compositor unavailable in headless bpy 5.2.3 (no node_tree); glare skipped")
        else:
            sc.use_nodes = True
            nodes.clear()
            render = nodes.new("CompositorNodeRLayers")
            comp = nodes.new("CompositorNodeComposite")
            glare_node = nodes.new("CompositorNodeGlare")
            glare_node.glare_type = "BLOOM"
            glare_node.mix = min(max(glare, 0.0), 1.0) * 0.9 - 0.45
            mix = nodes.new("CompositorNodeMixRGB")
            mix.inputs["Fac"].default_value = min(max(glare, 0.0), 1.0)
            links.new(render.outputs["Image"], mix.inputs[1])
            links.new(render.outputs["Image"], glare_node.inputs["Image"])
            links.new(glare_node.outputs["Image"], mix.inputs[2])
            links.new(mix.outputs["Image"], comp.inputs["Image"])
    if dof_fstop:
        sc.camera.data.dof.use_dof = True
        sc.camera.data.dof.focus_distance = (
            sc.camera.location - sc.camera.matrix_world.to_translation()
        ).length
        sc.camera.data.dof.aperture_fstop = dof_fstop
