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
