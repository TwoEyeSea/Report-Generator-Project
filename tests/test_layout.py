from decimal import Decimal

from tp_drawer.layout import band_y_range, compute_scale, y_at_depth


def test_compute_scale_fills_frame_height():
    scale = compute_scale(Decimal(88), 5.5)  # 88in real depth -> 5.5in of page
    assert scale == 5.5 / 88


def test_compute_scale_zero_depth():
    assert compute_scale(Decimal(0), 5.5) == 0.0


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
