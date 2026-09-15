from decimal import Decimal

from tp_drawer.layout import band_y_range, compute_scale, compute_scale_preferring_fixed, y_at_depth


def test_compute_scale_fills_frame_height():
    scale = compute_scale(Decimal(88), 5.5)  # 88in real depth -> 5.5in of page
    assert scale == 5.5 / 88


def test_compute_scale_zero_depth():
    assert compute_scale(Decimal(0), 5.5) == 0.0


def test_preferring_fixed_uses_fixed_scale_when_it_fits():
    # At fixed_scale=0.1, 20in of depth needs only 2.0in of page -- well
    # within the 5.5in frame, so the fixed scale is used as-is rather
    # than zooming in to fill the frame.
    scale = compute_scale_preferring_fixed(Decimal(20), 5.5, fixed_scale=0.1)
    assert scale == 0.1


def test_preferring_fixed_leaves_room_below_a_shallow_pit():
    # The whole point: a shallow pit's column shouldn't be stretched to
    # fill the frame just for being the deepest thing in its project.
    frame_top, frame_height, fixed_scale = 10.0, 5.5, 0.1
    scale = compute_scale_preferring_fixed(Decimal(20), frame_height, fixed_scale)
    y = y_at_depth(frame_top, scale, Decimal(20))
    assert y > frame_top - frame_height  # stops well above the frame's bottom edge


def test_preferring_fixed_falls_back_to_compute_scale_when_too_deep():
    # At fixed_scale=0.1, 88in of depth would need 8.8in of page -- more
    # than the 5.5in frame has -- so this falls back to compute_scale's
    # own "zoom to exactly fill the frame" ratio instead.
    max_depth, frame_height, fixed_scale = Decimal(88), 5.5, 0.1
    scale = compute_scale_preferring_fixed(max_depth, frame_height, fixed_scale)
    assert scale == compute_scale(max_depth, frame_height)
    assert scale != fixed_scale


def test_preferring_fixed_boundary_exactly_fits():
    # Exactly at the boundary (fixed_scale * depth == frame_height) should
    # still use the fixed scale, not fall back -- "<=", not "<".
    scale = compute_scale_preferring_fixed(Decimal(55), 5.5, fixed_scale=0.1)
    assert scale == 0.1


def test_preferring_fixed_zero_depth():
    assert compute_scale_preferring_fixed(Decimal(0), 5.5, fixed_scale=0.1) == 0.0


def test_y_at_depth_zero_is_frame_top():
    assert y_at_depth(10.0, 0.5, Decimal(0)) == 10.0


def test_y_at_depth_moves_down_with_depth():
    assert y_at_depth(10.0, 0.5, Decimal(4)) == 8.0


def test_deepest_pit_reaches_frame_bottom():
    frame_top, frame_height = 10.0, 4.0
    max_depth = Decimal(88)
    scale = compute_scale(max_depth, frame_height)
    assert y_at_depth(frame_top, scale, max_depth) == frame_top - frame_height


def test_shallower_pit_stops_above_frame_bottom():
    frame_top, frame_height = 10.0, 4.0
    scale = compute_scale(Decimal(88), frame_height)
    shallower_depth = Decimal(44)  # half the deepest pit's depth
    y = y_at_depth(frame_top, scale, shallower_depth)
    assert y == frame_top - frame_height / 2


def test_band_y_range_spans_a_layer():
    frame_top, scale = 10.0, 0.5
    y_top, y_bot = band_y_range(frame_top, scale, Decimal(0), Decimal(4))
    assert y_top == 10.0
    assert y_bot == 8.0
