"""Build rounded ceramic solids from offset rings of the shared flat master."""

import json
import math
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh

from logo_maker import pipeline

root = Path(__file__).parent
pipeline.prepare_motif(root)
data = json.loads((root / "motif.json").read_text())


def area(poly):
    return np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - poly[:, 1] * np.roll(poly[:, 0], -1)) / 2


def sample(poly, count, anchor):
    a = np.asarray(poly)
    b = np.roll(a, -1, axis=0)
    vec = b - a
    length = np.linalg.norm(vec, axis=1)
    keep = length > 1e-10
    a = a[keep]
    vec = vec[keep]
    length = length[keep]
    u = np.clip(np.sum((anchor - a) * vec, axis=1) / (length * length), 0, 1)
    closest = a + u[:, None] * vec
    k = np.argmin(np.linalg.norm(closest - anchor, axis=1))
    cumulative = np.r_[0, np.cumsum(length)]
    start = cumulative[k] + u[k] * length[k]
    distances = (start + np.arange(count) * cumulative[-1] / count) % cumulative[-1]
    idx = np.searchsorted(cumulative, distances, side="right") - 1
    return a[idx] + ((distances - cumulative[idx]) / length[idx])[:, None] * vec[idx]


def sculpt(layer, height, radius, zbase, out):
    contours = [
        np.array([[(x - 500) * 0.002, (500 - y) * 0.002] for x, y in c]) for c in layer["contours"]
    ]
    section = mf.CrossSection(contours, mf.FillRule.EvenOdd)
    base = sorted(section.to_polygons(), key=lambda p: -abs(area(p)))
    counts = [512 if i == 0 else 256 for i in range(len(base))]
    anchors = [p[np.lexsort((p[:, 1], p[:, 0]))[0]] for p in base]
    profiles = [
        (radius * (1 - math.cos(t)), radius * (1 - math.sin(t)))
        for t in np.linspace(0, math.pi / 2, 9)
    ]
    profiles += [
        (height - radius + radius * math.sin(t), radius * (1 - math.cos(t)))
        for t in np.linspace(0, math.pi / 2, 9)
    ]
    rings = []
    vertices = []
    for z, inset in profiles:
        polygons = sorted(
            section.offset(-inset, circular_segments=64).to_polygons(), key=lambda p: -abs(area(p))
        )
        if len(polygons) != len(base):
            raise ValueError("offset changed topology")
        ring = []
        for p, count, anchor, original in zip(polygons, counts, anchors, base, strict=True):
            if area(p) * area(original) < 0:
                p = p[::-1]
            ring.append(sample(p, count, anchor))
        rings.append(ring)
        vertices.extend((float(x), float(y), z + zbase) for p in ring for x, y in p)
    n = sum(counts)
    faces = []
    for level in range(len(rings) - 1):
        offset = 0
        for count in counts:
            for k in range(count):
                a = level * n + offset + k
                b = level * n + offset + (k + 1) % count
                faces.extend([(a, b, b + n), (a, b + n, a + n)])
            offset += count
    faces.extend(tuple(map(int, t[::-1])) for t in mf.triangulate(rings[0]))
    top = (len(rings) - 1) * n
    faces.extend(tuple(int(i) + top for i in t) for t in mf.triangulate(rings[-1]))
    mesh = trimesh.Trimesh(vertices=np.array(vertices), faces=np.array(faces), process=True)
    mesh.fix_normals()
    if not (mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0):
        raise ValueError("invalid closed ceramic mesh")
    mesh.export(root / out)
    print(out, len(mesh.vertices), len(mesh.faces), mesh.volume)


for layer in data["layers"]:
    if layer["id"] == "body":
        sculpt(layer, 0.2, 0.028, 0, "ceramic-body.ply")
    else:
        sculpt(layer, 0.004, 0.0006, 0.2, "ceramic-inlay.ply")
