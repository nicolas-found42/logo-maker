"""Host-side 3D geometry: every mesh logo-maker renders is built here with numpy,
trimesh, manifold3d, fontTools, and scikit-image — never inside the bpy subprocess.

The bpy builder (`logo_maker.blender`) only imports these meshes, assigns materials,
and places lights and cameras, so the Cycles render and every alternate renderer
export see byte-identical geometry.
"""

from __future__ import annotations

import math
import re
import tempfile
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import trimesh

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont
    from manifold3d import Manifold

# The motif's 1000-unit box maps to 2.0 scene units (radius-470 circle -> 0.94).
UNIT = 0.002


def to3(x: float, y: float) -> tuple[float, float]:
    """Motif coords (y down, origin top-left) -> scene coords (y up, origin center)."""
    return ((x - 500.0) * UNIT, -(y - 500.0) * UNIT)


def hex_to_linear(hexstr: str) -> tuple[float, float, float, float]:
    """sRGB `#RRGGBB` -> linear RGBA for Blender color inputs."""
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", hexstr.strip()):
        raise ValueError(f"expected #RRGGBB, got {hexstr!r}")
    h = hexstr.strip()[1:]
    rgb = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in rgb]
    return (lin[0], lin[1], lin[2], 1.0)


def camera_distance(radius: float, fov_y_rad: float, framing: float) -> float:
    """Distance along the view axis so a sphere of `radius` fills `framing` of the frame."""
    if radius <= 0:
        raise ValueError(f"radius must be positive, got {radius}")
    if not 0 < framing <= 1:
        raise ValueError(f"framing must be in (0, 1], got {framing}")
    return radius / (math.tan(fov_y_rad / 2.0) * framing)


def fov_from_lens(lens_mm: float, sensor_mm: float = 36.0) -> float:
    """Vertical field of view in radians for a lens and sensor height."""
    return 2.0 * math.atan(sensor_mm / (2.0 * lens_mm))


def frame_distance(
    corners: list[tuple[float, float, float]],
    tilt_rad: float,
    azim_rad: float,
    fov_y_rad: float,
    framing: float,
    aspect: float = 1.0,
) -> float:
    """Distance so every center-relative corner fits inside `framing` of the frame.

    Projects corners onto the camera right/up axes (camera tipped `tilt_rad` away
    from straight-on along the plate normal +Z, approaching from `azim_rad`)
    instead of fitting a bounding sphere, which leaves flat objects swimming in
    empty frame.
    """
    if fov_y_rad <= 0:
        raise ValueError(f"fov must be positive, got {fov_y_rad}")
    if not 0 < framing <= 1:
        raise ValueError(f"camera.framing must be in (0, 1], got {framing}")
    if aspect <= 0:
        raise ValueError(f"aspect must be positive, got {aspect}")
    tan_v = math.tan(fov_y_rad / 2.0)
    tan_h = tan_v * aspect
    sin_a, cos_a = math.sin(azim_rad), math.cos(azim_rad)
    sin_t, cos_t = math.sin(tilt_rad), math.cos(tilt_rad)
    right = (-cos_a, -sin_a, 0.0)
    up = (-sin_a * cos_t, cos_a * cos_t, sin_t)
    fwd = (sin_a * sin_t, -cos_a * sin_t, cos_t)
    need = 0.05
    for ox, oy, oz in corners:
        x = ox * right[0] + oy * right[1]
        y = ox * up[0] + oy * up[1] + oz * up[2]
        q = ox * fwd[0] + oy * fwd[1] + oz * fwd[2]
        need = max(need, abs(x) / (tan_h * framing) + q, abs(y) / (tan_v * framing) + q)
    return need


def ring_layout(
    text: str,
    advances: list[float],
    radius: float,
    size: float,
    start_angle: float = math.pi / 2,
    clockwise: bool = True,
) -> dict:
    """Lay `text` on a circle: fit the full ring, spread leftover as tracking.

    Returns per-character placement plus the size/tracking used. Characters never
    overlap: each occupies exactly advance*size + tracking of arc, and the arcs
    sum to the circumference within rounding error.
    """
    if len(text) != len(advances):
        raise ValueError(f"text length {len(text)} != advances length {len(advances)}")
    if radius <= 0:
        raise ValueError(f"radius must be positive, got {radius}")
    total = sum(advances)
    if total <= 0:
        raise ValueError("advances sum to zero; nothing to lay out")
    circumference = 2.0 * math.pi * radius
    size = min(size, circumference / total)  # shrink to fit, like a coin legend
    tracking = (circumference - total * size) / len(text)
    chars = []
    acc = 0.0
    direction = -1.0 if clockwise else 1.0
    for ch, adv in zip(text, advances, strict=True):
        width = adv * size + tracking
        mid = acc + width / 2.0
        angle = start_angle + direction * mid / radius
        chars.append(
            {
                "char": ch,
                "angle": angle,
                "x": radius * math.cos(angle),
                "y": radius * math.sin(angle),
                "rot_z": angle - math.pi / 2 if clockwise else angle + math.pi / 2,
                "arc": width,
            }
        )
        acc += width
    return {
        "chars": chars,
        "size": size,
        "tracking": tracking,
        "circumference": circumference,
        "total_arc": acc,
    }


def _manifold_to_trimesh(m: Manifold) -> trimesh.Trimesh:
    mesh = m.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    faces = np.asarray(mesh.tri_verts, dtype=np.int64)
    out = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    out.remove_infinite_values()
    return _orient_solid(out)


def _orient_solid(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Outward-facing normals: a solid's signed volume is positive."""
    if mesh.volume < 0:
        mesh.invert()
    return mesh


def _require_trimesh(mesh: object, op: str) -> trimesh.Trimesh:
    """Narrow trimesh's `Geometry` union: every builder here must yield one mesh."""
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"{op} produced {type(mesh).__name__}, not a single mesh")
    return mesh


def _weld_soup(tris: np.ndarray) -> trimesh.Trimesh:
    """Triangle soup (e.g. from a batched sampler) into one watertight solid."""
    mesh = trimesh.Trimesh(
        vertices=np.asarray(tris, dtype=np.float64).reshape(-1, 3),
        faces=np.arange(len(tris) * 3).reshape(-1, 3),
        process=False,
    )
    mesh.merge_vertices()
    faces = np.asarray(mesh.faces)
    faces = faces[np.asarray(mesh.area_faces) > 1e-12]
    _, keep = np.unique(np.sort(faces, axis=1), axis=0, return_index=True)
    out = trimesh.Trimesh(
        vertices=np.asarray(mesh.vertices), faces=faces[np.sort(keep)], process=True
    )
    out.merge_vertices()
    return out


def _point_in_poly(pt: np.ndarray, poly: np.ndarray) -> bool:
    """Ray-cast containment for one point against one closed polygon."""
    x, y = float(pt[0]), float(pt[1])
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = float(poly[i][0]), float(poly[i][1])
        x1, y1 = float(poly[(i + 1) % n][0]), float(poly[(i + 1) % n][1])
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def _signed_area(poly: np.ndarray) -> float:
    return (
        float(np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - np.roll(poly[:, 0], -1) * poly[:, 1]))
        / 2
    )


def _extrude(
    polygons: Sequence[Sequence[Sequence[float]]], z0: float, z1: float
) -> trimesh.Trimesh:
    """Extrude 2D contours into a watertight solid (even-odd nesting -> holes)."""
    from manifold3d import triangulate

    arrs = [
        np.asarray([[float(x), float(y)] for x, y in poly], dtype=np.float64)
        for poly in polygons
        if len(poly) >= 3
    ]
    if not arrs:
        raise ValueError("need at least one contour with 3+ points")
    if z1 == z0:
        raise ValueError("extrusion height must be nonzero")
    areas = [abs(_signed_area(a)) for a in arrs]
    order = sorted(range(len(arrs)), key=lambda i: areas[i])
    parent = [-1] * len(arrs)
    for rank, i in enumerate(order):
        for j in order[rank + 1 :]:
            if _point_in_poly(arrs[i][0], arrs[j]):
                parent[i] = j
                break
    depth = [0] * len(arrs)
    for i in order:
        if parent[i] >= 0:
            depth[i] = depth[parent[i]] + 1
    oriented: list[np.ndarray] = []
    for i, arr in enumerate(arrs):
        want_ccw = depth[i] % 2 == 0
        is_ccw = _signed_area(arr) > 0
        oriented.append(arr if want_ccw == is_ccw else arr[::-1])
    starts, flat = [], []
    for poly in oriented:
        starts.append(len(flat))
        flat.extend([list(p) for p in poly])
    tris = np.asarray(triangulate(oriented))
    cap = np.array(flat, dtype=np.float64)
    n = len(cap)
    verts = np.vstack(
        [np.hstack([cap, np.full((n, 1), z0)]), np.hstack([cap, np.full((n, 1), z1)])]
    )
    faces = [list(map(int, t[::-1])) for t in tris]  # bottom cap faces down
    faces += [[int(t[0] + n), int(t[1] + n), int(t[2] + n)] for t in tris]  # top faces up
    for poly, s in zip(oriented, starts, strict=True):
        m = len(poly)
        for k in range(m):
            b0, b1 = s + k, s + (k + 1) % m
            faces.append([b0, b1, b1 + n])
            faces.append([b0, b1 + n, b0 + n])
    mesh = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=True)
    mesh.merge_vertices()
    return _orient_solid(mesh)


def plate_mesh(
    radius: float = 1.0,
    thickness: float = 0.17,
    top_z: float = 0.17,
    edge: str = "smooth",
    seed: int = 0,
    holes: list[list[tuple[float, float]]] | None = None,
    segments: int = 256,
) -> trimesh.Trimesh:
    """A solid disc whose top sits at `top_z` (base at `top_z - thickness`)."""
    rng = np.random.default_rng(seed)
    phases = rng.uniform(0.0, 2.0 * math.pi, size=4)
    amps = (0.035, 0.022, 0.012, 0.006) if edge == "irregular" else (0.0, 0.0, 0.0, 0.0)
    freqs = (5, 9, 17, 31)
    outline = []
    for i in range(segments):
        th = 2.0 * math.pi * i / segments
        r = radius * (
            1.0 + sum(a * math.sin(f * th + p) for a, f, p in zip(amps, freqs, phases, strict=True))
        )
        outline.append((r * math.cos(th), r * math.sin(th)))
    polys = [outline] + [list(h) for h in (holes or [])]
    return _extrude(polys, top_z - thickness, top_z)


def relief_mesh(
    contours_1000: Sequence[Sequence[Sequence[float]]],
    height: float,
    base_z: float = 0.0,
    simplify_tol: float = 0.15,
) -> trimesh.Trimesh:
    polys = []
    for contour in contours_1000:
        pts = [to3(x, y) for x, y in contour]
        if len(pts) >= 3:
            polys.append(pts)
    return _extrude(polys, base_z, base_z + height)


def boolean_mesh(a: trimesh.Trimesh, b: trimesh.Trimesh, op: str) -> trimesh.Trimesh:
    """Combine two meshes with manifold booleans: `difference` | `union` | `intersection`."""
    from manifold3d import Manifold, Mesh

    def _to_manifold(t: trimesh.Trimesh) -> Manifold:
        return Manifold(
            Mesh(
                vert_properties=np.asarray(t.vertices, dtype=np.float32),
                tri_verts=np.asarray(t.faces, dtype=np.uint32),
            )
        )

    ma, mb = _to_manifold(a), _to_manifold(b)
    if op == "difference":
        out = ma - mb
    elif op == "union":
        out = ma + mb
    elif op == "intersection":
        out = ma ^ mb
    else:
        raise ValueError(f"unknown boolean op {op!r}; want difference|union|intersection")
    return _manifold_to_trimesh(out)


def rim_mesh(
    major: float, minor: float, z: float = 0.0, major_segments: int = 128, minor_segments: int = 24
) -> trimesh.Trimesh:
    """A torus ring (raised lip or border) centered at height `z`."""
    mesh = trimesh.creation.torus(major, minor)
    mesh.apply_translation((0.0, 0.0, z))
    return mesh


def ribbon_mesh(
    angle_deg: float = 0.0,
    length: float = 3.2,
    width: float = 0.4,
    z: float = -0.02,
    phase: float = 0.0,
    thickness: float = 0.012,
) -> trimesh.Trimesh:
    """A wavy strip with swallow-tail ends, stitched from hexagonal rings."""
    a = math.radians(angle_deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    steps = 64
    rings = []
    for i in range(steps + 1):
        t = -length / 2 + length * i / steps
        wave = 0.035 * math.sin(t * 2.6 + phase)
        droop = -0.06 * max(0.0, abs(t) - 0.9)
        c = np.array([d[0] * t, d[1] * t, z + wave + droop])
        mid = d * (width * 0.45 if i == 0 else (-width * 0.45 if i == steps else 0.0))
        hw, ht = width / 2, thickness / 2
        side_v = np.array([mid[0], mid[1], 0.0])
        left = np.array([n[0] * hw, n[1] * hw, 0.0])
        rings.append(
            np.array(
                [
                    c - left + [0.0, 0.0, ht],
                    c + side_v + [0.0, 0.0, ht],
                    c + left + [0.0, 0.0, ht],
                    c + left - [0.0, 0.0, ht],
                    c + side_v - [0.0, 0.0, ht],
                    c - left - [0.0, 0.0, ht],
                ]
            )
        )
    rings = np.array(rings)
    faces = []
    for i in range(steps):
        for k in range(6):
            k2 = (k + 1) % 6
            faces.append([i * 6 + k, i * 6 + k2, (i + 1) * 6 + k2])
            faces.append([i * 6 + k, (i + 1) * 6 + k2, (i + 1) * 6 + k])
    # End caps: fan over the hexagon (verts 0..5), flipped at the far end.
    for i, flip in ((0, True), (steps, False)):
        base = i * 6
        for k in range(1, 5):
            tri = [base, base + k + 1, base + k]
            faces.append(tri if flip else tri[::-1])
    mesh = trimesh.Trimesh(vertices=rings.reshape(-1, 3), faces=np.array(faces), process=True)
    mesh.merge_vertices()
    return _orient_solid(mesh)


def tube_mesh(
    contours_scene: Sequence[Sequence[Sequence[float]]],
    radius: float,
    z: float = 0.0,
    sides: int = 10,
) -> trimesh.Trimesh:
    """Sweep a round tube around each closed contour at height `z`, mitred at corners.

    Each ring lies in the plane bisecting its corner and is stretched across the
    corner by 1/cos(half-turn), so straight runs keep their full radius and
    corners join without twisting. Very sharp corners clamp the stretch at 4x.
    """
    ring = np.arange(sides) / sides * 2.0 * math.pi
    cos_r, sin_r = np.cos(ring), np.sin(ring)
    parts = []
    for contour in contours_scene:
        pts = np.array([(x, y) for x, y in contour], dtype=np.float64)
        if len(pts) >= 2:
            # Drop the repeated closing point and any zero-length steps.
            steps = np.linalg.norm(np.roll(pts, -1, axis=0) - pts, axis=1)
            pts = pts[steps > 1e-9]
        if len(pts) < 3:
            continue
        out = np.roll(pts, -1, axis=0) - pts  # segment leaving each vertex
        out /= np.linalg.norm(out, axis=1, keepdims=True)
        bisector = np.roll(out, 1, axis=0) + out
        lengths = np.linalg.norm(bisector, axis=1, keepdims=True)
        tangent = np.where(lengths > 1e-9, bisector / np.maximum(lengths, 1e-12), out)
        normal = np.stack([-tangent[:, 1], tangent[:, 0]], axis=1)  # in-plane, left of travel
        stretch = 1.0 / np.maximum(np.einsum("ij,ij->i", tangent, out), 0.25)
        across = normal[:, None, :] * (radius * stretch[:, None, None] * cos_r[None, :, None])
        verts = np.empty((len(pts), sides, 3))
        verts[..., :2] = pts[:, None, :] + across
        verts[..., 2] = z + radius * sin_r[None, :]
        rows = len(pts)
        faces = []
        for i in range(rows):
            j = (i + 1) % rows
            for k in range(sides):
                k2 = (k + 1) % sides
                faces.append([i * sides + k, j * sides + k, j * sides + k2])
                faces.append([i * sides + k, j * sides + k2, i * sides + k2])
        part = trimesh.Trimesh(vertices=verts.reshape(-1, 3), faces=np.array(faces), process=True)
        parts.append(_orient_solid(part))
    if not parts:
        raise ValueError("tube needs at least one contour with 3+ points")
    return _require_trimesh(trimesh.util.concatenate(parts), "tube")


def voxel_mesh(
    contours_1000: Sequence[Sequence[Sequence[float]]],
    cube: float = 0.07,
    height: float = 0.14,
    base_z: float = 0.0,
) -> trimesh.Trimesh:
    """Rasterize motif contours to filled cubes of edge `cube`, `height` tall."""
    from PIL import Image, ImageDraw

    res = 600
    img = Image.new("L", (res, res), 0)
    draw = ImageDraw.Draw(img)
    polys = [np.asarray(c, dtype=np.float64) for c in contours_1000 if len(c) >= 3]
    areas = [abs(_signed_area(p)) for p in polys]
    order = sorted(range(len(polys)), key=lambda i: areas[i])
    parent = [-1] * len(polys)
    for rank, i in enumerate(order):
        for j in order[rank + 1 :]:
            if _point_in_poly(polys[i][0], polys[j]):
                parent[i] = j
                break
    depth = [0] * len(polys)
    for i in order:
        if parent[i] >= 0:
            depth[i] = depth[parent[i]] + 1
    for poly, d in zip(polys, depth, strict=True):
        px = [((x / 1000.0) * res, (y / 1000.0) * res) for x, y in poly]
        draw.polygon(px, fill=255 if d % 2 == 0 else 0)
    mask = np.asarray(img) > 127
    xs = np.nonzero(mask)[1]
    if len(xs) == 0:
        raise ValueError("voxel mask is empty; contours cover nothing")
    boxes = []
    step = max(1, round(cube / (2.0 / res)))
    for gy in range(0, res, step):
        for gx in range(0, res, step):
            if mask[gy : gy + step, gx : gx + step].mean() > 0.5:
                cx = (gx + step / 2) / res * 2.0 - 1.0
                cy = -((gy + step / 2) / res * 2.0 - 1.0)
                box = trimesh.creation.box((cube * 0.92, cube * 0.92, height))
                box.apply_translation((cx, cy, base_z + height / 2))
                boxes.append(box)
    return _orient_solid(_require_trimesh(trimesh.util.concatenate(boxes), "voxels"))


def inflate_mesh(
    contours_1000: Sequence[Sequence[Sequence[float]]],
    puff: float = 0.16,
    base_z: float = 0.0,
    depth: float = 0.05,
    resolution: int = 180,
) -> trimesh.Trimesh:
    """Puffy relief: signed distance field of the mask, sampled with fogleman/sdf,
    then isotropically remeshed with PyMeshLab."""
    import sdf as sdf_lib
    from PIL import Image, ImageDraw
    from scipy.ndimage import distance_transform_edt, map_coordinates

    res = resolution
    img = Image.new("L", (res, res), 0)
    draw = ImageDraw.Draw(img)
    for contour in contours_1000:
        px = [((x / 1000.0) * res, (y / 1000.0) * res) for x, y in contour]
        if len(px) >= 3:
            draw.polygon(px, fill=255)
    inside = np.asarray(img, dtype=np.float64) > 127
    if not inside.any():
        raise ValueError("inflate mask is empty; contours cover nothing")
    sdf_in = distance_transform_edt(inside)
    sdf_out = distance_transform_edt(~inside)
    sdf = np.where(inside, sdf_in, -sdf_out) * (2.0 / res)
    fall = res / 10.0 * (2.0 / res)
    profile = np.clip(sdf / max(fall, 1e-9), 0.0, None)
    top = np.where(
        inside,
        puff * (1.0 - np.cos(np.clip(profile, 0.0, 1.0) * math.pi / 2.0)),
        -0.02 * np.clip(sdf_out / 3.0, 0.0, 1.0),
    )  # ramp to buried: no cliff, no sheet
    ys, xs = np.nonzero(inside)
    x0, x1 = xs.min() / res * 2.0 - 1.0, (xs.max() + 1) / res * 2.0 - 1.0
    y_hi = -((ys.min() / res) * 2.0 - 1.0)
    y_lo = -(((ys.max() + 1) / res) * 2.0 - 1.0)
    margin = 0.08
    bx = (x0 - margin, x1 + margin)
    by = (y_lo - margin, y_hi + margin)

    def field(pts: np.ndarray) -> np.ndarray:
        pts = np.asarray(pts, dtype=np.float64).reshape(-1, 3)
        gx = np.clip((pts[:, 0] + 1.0) / 2.0 * (res - 1), 0, res - 1)
        gy = np.clip((1.0 - pts[:, 1]) / 2.0 * (res - 1), 0, res - 1)
        height = map_coordinates(top, [gy, gx], order=1, mode="nearest")
        border = (
            np.minimum(
                np.minimum(pts[:, 0] - bx[0], bx[1] - pts[:, 0]),
                np.minimum(pts[:, 1] - by[0], by[1] - pts[:, 1]),
            )
            - 0.01
        )
        return np.minimum(np.minimum(height - pts[:, 2], pts[:, 2] + depth), border)

    solid = sdf_lib.SDF3(field)  # the relief as a composable signed distance field
    z_lo, z_hi = -depth * 1.6, puff * 1.05
    n_xy, n_z = res + 1, 72
    xs = np.linspace(bx[0], bx[1], n_xy)
    ys = np.linspace(by[0], by[1], n_xy)
    zs = np.linspace(z_lo, z_hi, n_z)
    grid_z, grid_y, grid_x = np.meshgrid(zs, ys, xs, indexing="ij")
    pts = np.stack([grid_x.ravel(), grid_y.ravel(), grid_z.ravel()], axis=1)
    volume = np.asarray(solid(pts), dtype=np.float64).reshape(n_z, n_xy, n_xy)
    from skimage.measure import marching_cubes

    verts, faces, _, _ = marching_cubes(
        volume, level=0.0, spacing=(zs[1] - zs[0], ys[1] - ys[0], xs[1] - xs[0])
    )
    zz, yy, xx = verts[:, 0], verts[:, 1], verts[:, 2]
    world = np.stack([bx[0] + xx, by[0] + yy, z_lo + zz], axis=1)
    mesh = trimesh.Trimesh(vertices=world, faces=faces, process=True)
    mesh.merge_vertices()
    mesh.vertices = np.asarray(mesh.vertices, dtype=np.float64) + np.array([0.0, 0.0, base_z])
    return _orient_solid(_remesh_isotropic(mesh, (bx[1] - bx[0]) / res))


def _remesh_isotropic(mesh: trimesh.Trimesh, targetlen: float) -> trimesh.Trimesh:
    """Even out triangle sizes with PyMeshLab; keeps the input when it cannot run."""
    try:
        import pymeshlab

        ms = pymeshlab.MeshSet()
        ms.add_mesh(
            pymeshlab.Mesh(
                vertex_matrix=np.asarray(mesh.vertices), face_matrix=np.asarray(mesh.faces)
            )
        )
    except Exception:
        return mesh
    try:
        ms.meshing_isotropic_explicit_remeshing(iterations=3, targetlen=targetlen)
        out = ms.current_mesh()
        remeshed = trimesh.Trimesh(
            vertices=np.asarray(out.vertex_matrix()),
            faces=np.asarray(out.face_matrix()),
            process=True,
        )
        return remeshed if remeshed.is_watertight else mesh
    except Exception:
        return mesh


def lathe_mesh(profile: list[list[float]], sections: int) -> trimesh.Trimesh:
    """Turn a simple radial section around Z, keeping its authored shoulder contours."""
    from shapely.geometry import Polygon

    section = Polygon(profile)
    if not section.is_valid or section.area <= 0:
        raise ValueError("lathe profile must enclose one simple nonzero area")
    axis_points = [point for point in profile if point[0] == 0]
    if axis_points and (profile[0][0] != 0 or profile[-1][0] != 0 or len(axis_points) != 2):
        raise ValueError("lathe profile may touch the axis at its two endpoints only")
    # Pass the closed outer contour in the winding required by trimesh.
    contour = np.asarray(section.exterior.coords)
    if not section.exterior.is_ccw:
        contour = contour[::-1]
    mesh = trimesh.creation.revolve(contour, sections=sections)
    if not mesh.is_volume:
        raise ValueError("lathe profile did not produce a closed solid")
    return mesh


def cad_mesh(spec: dict) -> trimesh.Trimesh:
    """A build123d solid from a primitive spec: {op, size/radius, center, ...}.

    `center` is the XY middle with the base resting on `center[2]` (default 0),
    applied host-side so every backend places the solid identically.
    """
    import build123d as bd

    op = spec.get("op", "box")
    center = tuple(spec.get("center", (0.0, 0.0, 0.0)))
    if op in ("box", "rounded_box"):
        size = list(spec.get("size", [1.0, 1.0, 0.2]))
        solid = bd.Box(*size)
        if op == "rounded_box":
            # Fillet the solid's own edges; an impossible radius keeps the sharp box.
            with suppress(Exception):
                solid = solid.fillet(min(size) * 0.12, solid.edges())
    elif op == "cylinder":
        height = spec.get("height", 0.2)
        solid = bd.Cylinder(spec.get("radius", 0.8), height)
    else:
        raise ValueError(f"unknown cad op {op!r}; want box|cylinder|rounded_box")
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "solid.stl")
        bd.export_stl(solid, path)
        mesh = _require_trimesh(trimesh.load(path, force="mesh"), "cad")
    lo, hi = (
        np.asarray(mesh.bounds[0], dtype=np.float64),
        np.asarray(mesh.bounds[1], dtype=np.float64),
    )
    mesh.apply_translation(
        [center[0] - (lo[0] + hi[0]) / 2, center[1] - (lo[1] + hi[1]) / 2, center[2] - lo[2]]
    )
    return _orient_solid(mesh)


def _font_upm(font: TTFont, font_path: str) -> float:
    """Units-per-em: fontTools sets head.unitsPerEm dynamically, so read it loosely."""
    upm = getattr(font["head"], "unitsPerEm", None)
    if upm is None:
        raise ValueError(f"{font_path} has no units-per-em")
    return float(upm)


def glyph_contours(font_path: str, char: str) -> list[list[tuple[float, float]]]:
    """Flatten one glyph outline to polylines in em units (y up), curves at 12 steps."""
    from fontTools.pens.basePen import BasePen
    from fontTools.ttLib import TTFont

    font = TTFont(font_path)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    if cmap is None:
        raise ValueError(f"{font_path} has no usable cmap")
    if ord(char) not in cmap:
        raise ValueError(f"{font_path} has no glyph for {char!r}")
    glyph = glyph_set[cmap[ord(char)]]

    class _Pen(BasePen):
        def __init__(self):  # type: ignore[no-untyped-def]
            super().__init__(glyph_set)
            self.polys: list[list[tuple[float, float]]] = []
            self.current: list[tuple[float, float]] = []

        def _moveTo(self, pt):
            if self.current:
                self.polys.append(self.current)
            self.current = [tuple(pt)]

        def _lineTo(self, pt):
            self.current.append(tuple(pt))

        def _curveToOne(self, pt1, pt2, pt3):
            p0 = np.array(self.current[-1])
            for t in np.linspace(0, 1, 13)[1:]:
                mt = 1 - t
                p = (
                    mt**3 * p0
                    + 3 * mt**2 * t * np.array(pt1)
                    + 3 * mt * t**2 * np.array(pt2)
                    + t**3 * np.array(pt3)
                )
                self.current.append((float(p[0]), float(p[1])))

        def _qCurveToOne(self, pt1, pt2):
            p0 = np.array(self.current[-1])
            for t in np.linspace(0, 1, 13)[1:]:
                mt = 1 - t
                p = mt**2 * p0 + 2 * mt * t * np.array(pt1) + t**2 * np.array(pt2)
                self.current.append((float(p[0]), float(p[1])))

        def _closePath(self):
            if self.current:
                self.polys.append(self.current)
                self.current = []

    pen = _Pen()
    glyph.draw(pen)
    if pen.current:
        pen.polys.append(pen.current)
    upm = _font_upm(font, font_path)
    return [[(x / upm, y / upm) for x, y in poly] for poly in pen.polys if len(poly) >= 3]


def glyph_advance(font_path: str, char: str) -> float:
    """Advance width of one glyph in em units."""
    from fontTools.ttLib import TTFont

    font = TTFont(font_path)
    cmap = font.getBestCmap()
    if cmap is None:
        return 0.5
    if ord(char) not in cmap:
        return 0.5
    name = cmap[ord(char)]
    return font["hmtx"][name][0] / _font_upm(font, font_path)


def ring_text_mesh(
    font_path: str, text: str, radius: float, cap_height: float, base_z: float, extrude: float
) -> trimesh.Trimesh:
    """One extruded mesh: glyphs placed by `ring_layout`, y-up scene coords."""
    advances = [glyph_advance(font_path, ch) if ch != " " else 0.3 for ch in text]
    size = cap_height / 0.714  # same cap-height convention as the reference scene
    layout = ring_layout(text, advances, radius, size)
    size = layout["size"]
    parts = []
    for placement, ch in zip(layout["chars"], text, strict=True):
        if ch == " ":
            continue
        contours = glyph_contours(font_path, ch)
        polys = [[(x * size, y * size) for x, y in poly] for poly in contours]
        if not polys:
            continue
        mesh = _extrude(polys, 0.0, extrude)
        # Local glyph origin is the baseline start; center it, then rotate/translate.
        bounds = mesh.bounds
        mesh.apply_translation((-(bounds[0][0] + bounds[1][0]) / 2, 0.0, 0.0))
        cos_a, sin_a = math.cos(placement["rot_z"]), math.sin(placement["rot_z"])
        mat = np.eye(4)
        mat[:3, :3] = np.array([[cos_a, -sin_a, 0.0], [sin_a, cos_a, 0.0], [0.0, 0.0, 1.0]])
        mat[:3, 3] = (placement["x"], placement["y"], base_z)
        mesh.apply_transform(mat)
        parts.append(mesh)
    if not parts:
        raise ValueError(f"ring text {text!r} produced no geometry")
    return _orient_solid(_require_trimesh(trimesh.util.concatenate(parts), "ring text"))


def save_ply(mesh: trimesh.Trimesh, path: Path) -> Path:
    """Write a triangulated, normal-carrying PLY in world coords (host or bpy side)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(mesh, trimesh.Trimesh):
        raise TypeError(f"expected a Trimesh, got {type(mesh).__name__}")
    mesh.export(path)
    return path
