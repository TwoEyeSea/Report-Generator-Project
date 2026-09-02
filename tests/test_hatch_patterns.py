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


def test_gravel_pattern_is_mostly_angular_polygons_with_some_rounded_grains():
    dots = PATTERN_REGISTRY["dots"].generate(2.0, 1.5, 0.0, 1.0)
    gravel = PATTERN_REGISTRY["gravel"].generate(2.0, 1.5, 0.0, 1.0)
    assert len(gravel) > 0
    assert all(isinstance(p, (Dot, Blob)) for p in gravel)
    assert all(not p.filled for p in gravel if isinstance(p, Dot))
    blob_count = sum(isinstance(p, Blob) for p in gravel)
    dot_count = sum(isinstance(p, Dot) for p in gravel)
    assert dot_count > 0
    assert blob_count > dot_count  # most grains should be angular polygons, not round
    # grains vary in size rather than being a uniform grid of identical circles
    radii = {round(p.r, 6) for p in gravel if isinstance(p, Dot)}
    assert len(radii) > 1
    circle_dots = [p for p in gravel if isinstance(p, Dot)]
    assert circle_dots[0].r > dots[0].r


def test_gravel_pattern_is_deterministic_for_the_same_inputs():
    first = PATTERN_REGISTRY["gravel"].generate(2.0, 1.5, 0.0, 1.0)
    second = PATTERN_REGISTRY["gravel"].generate(2.0, 1.5, 0.0, 1.0)
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


def test_gravel_pattern_polygon_vertices_stay_within_their_packing_radius():
    """Every Blob's vertices must stay inside its allocated packing circle -- otherwise an
    angular grain could poke into a neighbor's space even though the underlying packer never
    overlaps circles. _generate_circles consumes its rng in the same order _pack_grains does
    (packing first, then shape choice/vertices per grain), so re-running _pack_grains with a
    freshly seeded rng reproduces the exact same grain list, index-for-index."""
    width, height, angle, size = 3.0, 3.0, 0.0, 1.25
    spacing = max(size, 0.01) * 0.4
    u, v = _axes(angle)
    grains = _pack_grains(width, height, spacing, u, v, random.Random(_PATTERN_SEED))

    gravel = PATTERN_REGISTRY["gravel"].generate(width, height, angle, size)
    assert len(gravel) == len(grains)

    for primitive, (gx, gy, radius) in zip(gravel, grains):
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


def test_native_marl_pattern_combines_a_line_family_with_a_dot_grid():
    dots_only = PATTERN_REGISTRY["dots"].generate(2.0, 2.0, 45.0, 1.0)
    combined = PATTERN_REGISTRY["native_marl"].generate(2.0, 2.0, 45.0, 1.0)

    lines = [p for p in combined if isinstance(p, LineSegment)]
    dots = [p for p in combined if isinstance(p, Dot)]
    assert all(isinstance(p, (LineSegment, Dot)) for p in combined)
    assert len(lines) > 0
    # Same dot grid as the plain "dots" pattern -- native_marl reuses
    # _generate_dots outright rather than re-deriving its own dot spacing.
    assert len(dots) == len(dots_only)

    # The line family runs along a single direction (not cross-hatched).
    angles = {round(math.degrees(math.atan2(s.y2 - s.y1, s.x2 - s.x1)) % 180, 3) for s in lines}
    assert len(angles) == 1


def test_organic_pattern_produces_paired_tick_segments():
    segments = PATTERN_REGISTRY["organic"].generate(2.0, 2.0, 0.0, 1.0)
    assert len(segments) > 0
    assert len(segments) % 2 == 0


def test_organic_frond_pattern_produces_six_lines_per_frond_in_a_symmetric_fan():
    width, height, angle, size = 3.0, 3.0, 0.0, 1.0
    segments = PATTERN_REGISTRY["organic_frond"].generate(width, height, angle, size)
    assert all(isinstance(s, LineSegment) for s in segments)
    assert len(segments) % 6 == 0  # base, height line, 2x 1/3-lines, 2x 2/3-lines, per frond

    row_spacing = max(size, 0.2) * 1.0
    h = row_spacing / 3.3

    # Generation order per frond: base, height line, left-1/3, right-1/3, left-2/3, right-2/3.
    base, height_line, left_third, right_third, left_two_thirds, right_two_thirds = segments[:6]

    # The base is one flat segment spanning the full 3h width (not two
    # separate P-to-corner segments).
    assert base.y1 == pytest.approx(base.y2)
    assert abs(base.x2 - base.x1) == pytest.approx(3 * h)

    # P (where the five non-base lines all start) is the base's midpoint.
    p = (height_line.x1, height_line.y1)
    assert p[0] == pytest.approx((base.x1 + base.x2) / 2)
    assert p[1] == pytest.approx(base.y1)
    for seg in (left_third, right_third, left_two_thirds, right_two_thirds):
        assert (seg.x1, seg.y1) == pytest.approx(p)

    # The height line goes straight up (along v, angle=0 here) by exactly h.
    assert height_line.x2 == pytest.approx(p[0])
    assert height_line.y2 == pytest.approx(p[1] + h)

    # 1/3 and 2/3 points are mirror images of each other across the height axis...
    assert left_third.x2 == pytest.approx(2 * p[0] - right_third.x2)
    assert left_third.y2 == pytest.approx(right_third.y2)
    assert left_two_thirds.x2 == pytest.approx(2 * p[0] - right_two_thirds.x2)
    assert left_two_thirds.y2 == pytest.approx(right_two_thirds.y2)
    # ...and the 2/3 points sit farther up (closer to the apex) than the 1/3 points.
    assert right_two_thirds.y2 > right_third.y2 > p[1]

    # Columns (lateral, u) are spaced wider than rows (v) -- fronds were
    # reported as laterally too close together on a square grid; this
    # confirms the fix actually widens column spacing, not row spacing too.
    all_p = [(segments[i + 1].x1, segments[i + 1].y1) for i in range(0, len(segments), 6)]
    xs = sorted({round(x, 6) for x, _ in all_p})
    ys = sorted({round(y, 6) for _, y in all_p})
    column_gap = xs[1] - xs[0]
    row_gap = ys[1] - ys[0]
    assert column_gap > row_gap
    assert column_gap == pytest.approx(row_spacing * 1.3)
    assert row_gap == pytest.approx(row_spacing)


def test_brick_pattern_produces_horizontal_rows_and_vertical_joints():
    segments = PATTERN_REGISTRY["brick"].generate(3.0, 3.0, 0.0, 1.0)
    assert len(segments) > 0


def test_every_registered_pattern_id_matches_its_key():
    for key, pattern in PATTERN_REGISTRY.items():
        assert pattern.id == key
