"""Host geometry: coordinate mapping, framing math, watertight solids, holes."""

from __future__ import annotations

import math

import pytest

from logo_maker import geometry as g


def test_hex_to_linear_known_values():
    assert g.hex_to_linear("#000000") == (0.0, 0.0, 0.0, 1.0)
    assert g.hex_to_linear("#FFFFFF") == (1.0, 1.0, 1.0, 1.0)
    r = g.hex_to_linear("#808080")[0]
    assert r == pytest.approx(0.2158, abs=1e-3)
    with pytest.raises(ValueError, match="expected #RRGGBB"):
        g.hex_to_linear("#12345")


def test_motif_mapping():
    assert g.to3(500, 500) == (0.0, 0.0)
    assert g.to3(1000, 0) == (1.0, 1.0)
    assert g.to3(0, 1000) == (-1.0, -1.0)


def test_framing_math():
    dist = g.camera_distance(1.0, math.radians(30), 1.0)
    assert dist == pytest.approx(1.0 / math.tan(math.radians(15)))
    assert g.camera_distance(1.0, 0.5, 0.5) == 2 * g.camera_distance(1.0, 0.5, 1.0)
    with pytest.raises(ValueError, match="radius must be positive"):
        g.camera_distance(0.0, 0.5, 0.8)
    with pytest.raises(ValueError, match="framing must be in"):
        g.camera_distance(1.0, 0.5, 1.5)


def test_frame_distance_tilt_is_angle_from_plate_normal():
    fov = math.radians(90)  # tan(fov/2) = 1, so distance = screen extent + depth toward camera
    for az in (0.0, 1.0, 2.5):
        # Tilt 0 looks straight down +Z from any azimuth: height on the axis is pure depth.
        assert g.frame_distance([(0, 0, 0.5)], 0.0, az, fov, 1.0) == pytest.approx(0.5)
    assert g.frame_distance([(1, 1, 0.5)], 0.0, 0.0, fov, 1.0) == pytest.approx(1.5)
    # Tilt 90 at azimuth 0 views the edge from -Y: height becomes screen-up extent.
    assert g.frame_distance([(0, 0, 0.7)], math.pi / 2, 0.0, fov, 1.0) == pytest.approx(0.7)
    assert g.frame_distance([(0, -0.7, 0)], math.pi / 2, 0.0, fov, 1.0) == pytest.approx(0.7)


def test_plate_solid_and_holes():
    plain = g.plate_mesh()
    assert plain.is_watertight
    assert plain.volume == pytest.approx(math.pi * 0.17, rel=0.02)
    holed = g.plate_mesh(holes=[[(0.2, 0), (0, 0.2), (-0.2, 0), (0, -0.2)]])
    assert holed.volume < plain.volume
    import numpy as np

    assert not np.allclose(
        g.plate_mesh(edge="irregular", seed=1).vertices,
        g.plate_mesh(edge="irregular", seed=2).vertices,
    )


def test_extrude_even_odd_hole():
    outer = [[0, 0], [1, 0], [1, 1], [0, 1]]
    hole = [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]]
    mesh = g._extrude([outer, hole], 0.0, 0.1)
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx((1 - 0.25) * 0.1, rel=0.02)
    with pytest.raises(ValueError, match="at least one contour"):
        g._extrude([[[0, 0]]], 0.0, 0.1)


def test_boolean_volumes():
    a = g.plate_mesh()
    wall = g.plate_mesh(radius=2.0, thickness=0.34, top_z=0.34)
    assert g.boolean_mesh(wall, a, "difference").is_watertight
    assert g.boolean_mesh(a, a, "union").volume == pytest.approx(a.volume, rel=1e-3)
    with pytest.raises(ValueError, match="unknown boolean op"):
        g.boolean_mesh(a, a, "xor")


def test_tube_keeps_full_round_section_through_corners():
    # Motif outlines repeat their first point; corners are mitred, never twisted flat,
    # so the sweep holds exactly centerline length x ring area.
    square = [(0.5, 0.5), (-0.5, 0.5), (-0.5, -0.5), (0.5, -0.5), (0.5, 0.5)]
    radius, sides = 0.05, 10
    tube = g.tube_mesh([square], radius, sides=sides)
    ring_area = sides / 2 * radius**2 * math.sin(2 * math.pi / sides)
    assert tube.is_watertight
    assert tube.volume == pytest.approx(4.0 * ring_area, rel=1e-6)
    assert tube.bounds[1][:2] == pytest.approx([0.55, 0.55])


def test_sweeps_and_solids_watertight():
    assert g.rim_mesh(0.85, 0.03).is_watertight
    assert g.ribbon_mesh(-28).is_watertight
    assert g.tube_mesh([[(0.5, 0), (0, -0.5), (-0.5, 0), (0, 0.5)]], 0.03).is_watertight
    assert g.cad_mesh({"op": "cylinder", "radius": 0.8, "height": 0.2}).is_watertight
    square = [[[100, 100], [900, 100], [900, 900], [100, 900]]]
    assert g.voxel_mesh(square).is_watertight
    assert g.inflate_mesh(square, resolution=60).is_watertight
    assert g.relief_mesh(square, 0.03, 0.1).is_watertight
    with pytest.raises(ValueError, match="voxel mask is empty"):
        g.voxel_mesh([[[0, 0]]])
