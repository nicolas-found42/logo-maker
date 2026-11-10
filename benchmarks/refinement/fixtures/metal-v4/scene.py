import bpy


def build(ctx):
    # Preserve planar machined caps; interpolated cap normals caused radial pinching.
    for obj in bpy.context.collection.objects:
        if obj.type == "MESH":
            for polygon in obj.data.polygons:
                polygon.use_smooth = False
            for modifier in obj.modifiers:
                if modifier.type == "BEVEL":
                    modifier.harden_normals = True

    # Define one brushing direction on the machined caps instead of implicit radial tangents.
    for material in ctx.materials.values():
        for node in list(material.node_tree.nodes):
            if node.type == "BSDF_PRINCIPLED":
                tangent = material.node_tree.nodes.new("ShaderNodeCombineXYZ")
                tangent.inputs["X"].default_value = 1.0
                material.node_tree.links.new(tangent.outputs["Vector"], node.inputs["Tangent"])
