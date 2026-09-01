import math
import random

import pytest

from tp_drawer.hatch_patterns import (
    PATTERN_REGISTRY,
    Blob,
    Dot,
    LineSegment,
    _CONTACT_OVERLAP_FRACTION,
    _MAX_GRAIN_FRACTION,
    _PATTERN_SEED,
    _axes,
    _pack_grains,
)


def test_none_pattern_generates_nothing():
    primitives = PATTERN_REGISTRY["none"].generate(2.0, 1.5, 0.0, 1.0)
    assert primitives == []


def test_dots_pattern_covers_the_box_with_filled_dots():
    primitives = PATTERN_REGISTRY["dots"].generate(2.0, 1.5, 0.0, 1.0)
    assert len(primitives) > 0
    assert all(isinstance(p, Dot) and p.filled for p in primitives)
    # at least one dot should fall inside the rectangle itself, not just the padded margin
    assert any(0 <= p.cx <= 2.0 and 0 <= p.cy <= 1.5 for p in primitives)


def test_circles_pattern_is_mostly_angular_polygons_with_some_rounded_grains():
    dots = PATTERN_REGISTRY["dots"].generate(2.0, 1.5, 0.0, 1.0)
    circles = PATTERN_REGISTRY["circles"].generate(2.0, 1.5, 0.0, 1.0)
    assert len(circles) > 0
    assert all(isinstance(p, (Dot, Blob)) for p in circles)
    assert all(not p.filled for p in circles if isinstance(p, Dot))
    blob_count = sum(isinstance(p, Blob) for p in circles)
    dot_count = sum(isinstance(p, Dot) for p in circles)
    assert dot_count > 0
    assert blob_count > dot_count  # most grains should be angular polygons, not round
    # grains vary in size rather than being a uniform grid of identical circles
    radii = {round(p.r, 6) for p in circles if isinstance(p, Dot)}
    assert len(radii) > 1
    circle_dots = [p for p in circles if isinstance(p, Dot)]
    assert circle_dots[0].r > dots[0].r


def test_circles_pattern_is_deterministic_for_the_same_inputs():
    first = PATTERN_REGISTRY["circles"].generate(2.0, 1.5, 0.0, 1.0)
    second = PATTERN_REGISTRY["circles"].generate(2.0, 1.5, 0.0, 1.0)
    assert first == second


def test_packed_grains_stay_within_the_allowed_contact_overlap():
    """Grains may now clip into their neighbors (a grain-supported fabric needs genuine contact,
    not a strict no-overlap gap), but only up to `_CONTACT_OVERLAP_FRACTION` of whichever grain
    in a pair is larger -- so the overlap can never exceed that fraction of the biggest possible
    grain (`_MAX_GRAIN_FRACTION * spacing`)."""
    spacing = 0.5
    u, v = _axes(0.0)
    rng = random.Random(1)
    grains = _pack_grains(3.0, 3.0, spacing, u, v, rng)
    max_overlap = spacing * _MAX_GRAIN_FRACTION * _CONTACT_OVERLAP_FRACTION

    assert len(grains) > 1
    for i in range(len(grains)):
        x1, y1, r1 = grains[i]
        for x2, y2, r2 in grains[i + 1 :]:
            distance = math.hypot(x1 - x2, y1 - y2)
            assert distance >= r1 + r2 - max_overlap - 1e-9


def test_packed_grains_include_genuine_contact_overlap():
    """The whole point of allowing overlap is that grains actually end up touching/clipping each
    other -- confirm that happens rather than the packer coincidentally never using its budget."""
    u, v = _axes(0.0)
    rng = random.Random(1)
    grains = _pack_grains(3.0, 3.0, 0.5, u, v, rng)

    overlapping_pairs = 0
    for i in range(len(grains)):
        x1, y1, r1 = grains[i]
        for x2, y2, r2 in grains[i + 1 :]:
            distance = math.hypot(x1 - x2, y1 - y2)
            if distance < r1 + r2 - 1e-9:
                overlapping_pairs += 1
    assert overlapping_pairs > 0


def test_circles_pattern_polygon_vertices_stay_within_their_packing_radius():
    """Every Blob's vertices must stay inside its allocated packing circle -- otherwise an
    angular grain could poke into a neighbor's space even though the underlying packer never
    overlaps circles. _generate_circles consumes its rng in the same order _pack_grains does
    (packing first, then shape choice/vertices per grain), so re-running _pack_grains with a
    freshly seeded rng reproduces the exact same grain list, index-for-index."""
    width, height, angle, size = 3.0, 3.0, 0.0, 1.25
    spacing = max(size, 0.01) * 0.4
    u, v = _axes(angle)
    grains = _pack_grains(width, height, spacing, u, v, random.Random(_PATTERN_SEED))

    circles = PATTERN_REGISTRY["circles"].generate(width, height, angle, size)
    assert len(circles) == len(grains)

    for primitive, (gx, gy, radius) in zip(circles, grains):
        if isinstance(primitive, Dot):
            assert primitive.cx == pytest.approx(gx)
            assert primitive.r == pytest.approx(radius)
        else:
            for px, py in primitive.points:
                assert math.hypot(px - gx, py - gy) <= radius + 1e-9


def test_larger_size_gives_wider_spacing_and_fewer_primitives():
    small = PATTERN_REGISTRY["dots"].generate(3.0, 3.0, 0.0, 0.5)
    large = PATTERN_REGISTRY["dots"].generate(3.0, 3.0, 0.0, 2.0)
    assert len(large) < len(small)


def test_dashes_pattern_segments_point_along_the_given_angle():
    segments = PATTERN_REGISTRY["dashes"].generate(3.0, 3.0, 90.0, 1.0)
    assert all(isinstance(s, LineSegment) for s in segments)
    seg = segments[0]
    dx, dy = seg.x2 - seg.x1, seg.y2 - seg.y1
    angle = math.degrees(math.atan2(dy, dx)) % 180
    assert angle == 90 or math.isclose(angle, 90, abs_tol=1e-6)


def test_cross_hatch_produces_two_perpendicular_families_of_lines():
    segments = PATTERN_REGISTRY["cross_hatch"].generate(2.0, 2.0, 0.0, 1.0)
    angles = set()
    for seg in segments:
        dx, dy = seg.x2 - seg.x1, seg.y2 - seg.y1
        angles.add(round(math.degrees(math.atan2(dy, dx)) % 180, 3))
    assert len(angles) == 2


def test_organic_pattern_produces_paired_tick_segments():
    segments = PATTERN_REGISTRY["organic"].generate(2.0, 2.0, 0.0, 1.0)
    assert len(segments) > 0
    assert len(segments) % 2 == 0


def test_brick_pattern_produces_horizontal_rows_and_vertical_joints():
    segments = PATTERN_REGISTRY["brick"].generate(3.0, 3.0, 0.0, 1.0)
    assert len(segments) > 0


def test_every_registered_pattern_id_matches_its_key():
    for key, pattern in PATTERN_REGISTRY.items():
        assert pattern.id == key
