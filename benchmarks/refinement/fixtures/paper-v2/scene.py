"""Heavyweight paper mesh with genuine changes of plane and layered edges.

Catalog layers cannot express folded/curved faces. This build(ctx) component
uses the same original polygons as motif.py and subdivides their faces to
resolve the crease. No imported or traced artwork.
"""

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

GEOMETRY = {
    "fold": "folio",
    "parts": [
        {
            "id": "left-leaf",
            "role": "primary",
            "points": [[180, 250], [465, 335], [465, 765], [180, 655]],
        },
        {
            "id": "shared-leaf",
            "role": "secondary",
            "points": [[510, 335], [700, 235], [805, 330], [805, 655], [510, 765]],
        },
        {"id": "turned-corner", "role": "primary", "points": [[700, 235], [805, 330], [700, 350]]},
    ],
}


def build(ctx):
    # Balance the catalog studio rig for very light sage stock.
    for light in ctx.scene.objects:
        if light.type == "LIGHT":
            light.data.energy *= 0.55
    if ctx.scene.world and ctx.scene.world.use_nodes:
        for node in ctx.scene.world.node_tree.nodes:
            if node.type == "BACKGROUND":
                node.inputs["Strength"].default_value *= 0.55
    data = GEOMETRY

    def elevation(x, y, part):
        if data["fold"] == "folio":
            if part == 2:
                return 0.31 + 0.10 * (805 - x) / 105
            return 0.08 + 0.30 * abs(x - 490) / 315 + 0.10 * max(0, (310 - x) / 130)
        if data["fold"] == "saddle":
            return 0.17 + 0.18 * abs((x + y - 1000) / 600)
        if data["fold"] == "scoop":
            return 0.14 + 0.06 * ((x - 500) / 300) ** 2
        if part == 0:
            return 0.27
        if part == 1:
            return 0.27 - 0.15 * max(0, min(1, (y - 370) / 260))
        return 0.12

    def split(tri, depth):
        if depth == 0:
            return [tri]
        a, b, c = tri
        ab = (a + b) / 2
        bc = (b + c) / 2
        ca = (c + a) / 2
        return [
            small
            for t in [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
            for small in split(t, depth - 1)
        ]

    for part_index, part in enumerate(data["parts"]):
        outline = [Vector((float(x), float(y), 0)) for x, y in part["points"]]
        raw = tessellate_polygon([outline])
        tris = [tuple(outline[p] if isinstance(p, int) else p for p in tri) for tri in raw]
        triangles = [small for tri in tris for small in split(tri, 3)]
        for sheet in range(1):
            vertices = []
            faces = []
            indices = {}

            def index(
                point, side, indices=indices, part_index=part_index, sheet=sheet, vertices=vertices
            ):
                x, y = point[0], point[1]
                key = (round(x, 5), round(y, 5), side)
                if key not in indices:
                    z = elevation(x, y, part_index) - sheet * 0.021 - side * 0.034
                    indices[key] = len(vertices)
                    vertices.append(((x - 500) / 500, (500 - y) / 500, z))
                return indices[key]

            edge_counts = {}
            for tri in triangles:
                top = [index(p, 0) for p in tri]
                bottom = [index(p, 1) for p in tri]
                # Input uses SVG's downward Y; reverse its winding in scene space.
                faces.append(tuple(reversed(top)))
                faces.append(tuple(bottom))
                for a, b in zip(top, top[1:] + top[:1], strict=True):
                    key = tuple(sorted((a, b)))
                    edge_counts[key] = edge_counts.get(key, 0) + 1
            inverse = {v: k for k, v in indices.items()}
            for (a, b), count in edge_counts.items():
                if count == 1:
                    pa = inverse[a]
                    pb = inverse[b]
                    aa = indices[(pa[0], pa[1], 1)]
                    bb = indices[(pb[0], pb[1], 1)]
                    faces.append((a, b, bb, aa))
            mesh = bpy.data.meshes.new(f"{part['id']}-sheet-{sheet}")
            mesh.from_pydata(vertices, [], faces)
            mesh.update()
            obj = bpy.data.objects.new(mesh.name, mesh)
            ctx.link(obj)
            role = part["role"] if sheet == 0 else "surface"
            obj.data.materials.append(ctx.materials[role])
            # Keep the deliberate folds and cut edges crisp; material fibers do the texture.
            for poly in mesh.polygons:
                poly.use_smooth = False
