"""Ring text fit: the characters span the whole circle, never overlap, and the
arcs sum to the circumference within rounding error.
"""

from __future__ import annotations

import math
from itertools import pairwise

import pytest

from logo_maker.geometry import ring_layout


def test_arcs_sum_to_circumference():
    layout = ring_layout("HELLO", [0.7, 0.6, 0.65, 0.65, 0.7], 0.7, 0.1)
    assert layout["total_arc"] == pytest.approx(layout["circumference"], rel=1e-9)
    assert layout["tracking"] >= 0


def test_no_overlap_and_monotonic():
    layout = ring_layout("ABCDE", [0.6] * 5, 0.7, 0.1)
    angles = [c["angle"] for c in layout["chars"]]
    assert all(a > 0 for c in layout["chars"] for a in [c["arc"]])
    assert all(earlier > later for earlier, later in pairwise(angles))  # clockwise
    gaps = [a - b for a, b in pairwise(angles)]
    assert min(gaps) > 0


def test_long_text_shrinks_to_fit():
    layout = ring_layout("X" * 60, [0.7] * 60, 0.5, 0.1)
    assert layout["size"] < 0.1
    assert layout["total_arc"] == pytest.approx(layout["circumference"], rel=1e-9)


def test_short_text_spreads_tracking():
    tight = ring_layout("AB", [0.6, 0.6], 0.7, 0.1)
    wide = ring_layout("AB", [0.6, 0.6], 1.4, 0.1)
    assert wide["tracking"] > tight["tracking"]


def test_positions_on_radius():
    layout = ring_layout("AB", [0.6, 0.7], 0.655, 0.1)
    for char in layout["chars"]:
        assert math.hypot(char["x"], char["y"]) == pytest.approx(0.655, rel=1e-9)

    with pytest.raises(ValueError, match="text length"):
        ring_layout("ABC", [0.5, 0.5], 0.7, 0.1)
    with pytest.raises(ValueError, match="sum to zero"):
        ring_layout("A", [0.0], 0.7, 0.1)
    with pytest.raises(ValueError, match="radius must be positive"):
        ring_layout("A", [0.5], 0.0, 0.7)
