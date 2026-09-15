"""Pure geometry math for the true-to-scale stratigraphy column.

All pits in a single build share one scale. That scale is normally a
fixed, real-world-comparable one (see compute_scale_preferring_fixed) --
only a pit too deep to fit the page frame at that fixed scale forces a
"zoom out" via compute_scale, just enough for the deepest pit's column to
exactly fill the frame height. Shallower pits always draw proportionally
shorter columns than the deepest one, so relative depth between pits
reads correctly on the page either way.

No matplotlib imports here so this stays trivially unit-testable.

WHY "no matplotlib imports" MATTERS:
This file only does arithmetic -- it takes real-world depths (in inches)
and works out where on the page (in inches of paper) they should land. It
never touches matplotlib, so a test can call these functions with plain
numbers and check the plain numbers that come back, with no PDF, no
figure, and no drawing involved. That's much faster and more reliable
than a test that has to render an actual page image and inspect pixels.
See tests/test_layout.py for exactly that kind of test. This "keep the
math separate from the drawing" split is a common technique for making
otherwise-hard-to-test graphical code testable.
"""

from decimal import Decimal


def compute_scale(max_depth_in: Decimal, frame_height: float) -> float:
    """Page-inches per real inch of depth, sized so max_depth_in fills frame_height.

    This is the "how many page-inches equal one real inch" conversion
    factor -- e.g. if the deepest pit is 120 real inches deep and the
    frame is only 6 page-inches tall, the scale works out to 0.05, so
    every real inch of depth becomes 0.05 inches on the page. Every other
    depth-to-page-position calculation in the program (see y_at_depth
    below) multiplies by this one number, which is what keeps every pit
    in the project drawn at the same, mutually comparable scale.
    """
    if max_depth_in <= 0:
        # A pit with no recorded depth yet (e.g. mid-data-entry) shouldn't
        # crash the whole scale calculation with a division by zero --
        # 0.0 is a safe "not drawable yet" placeholder.
        return 0.0
    return frame_height / float(max_depth_in)


def compute_scale_preferring_fixed(max_depth_in: Decimal, frame_height: float, fixed_scale: float) -> float:
    """Like compute_scale, but prefers a fixed, real-world-comparable
    scale (page-inches per real inch of depth) whenever the deepest pit
    fits within frame_height at that scale -- only falling back to
    compute_scale's own "zoom until it exactly fills the frame" ratio
    once the fixed scale would genuinely overflow the page.

    Without this, a shallow pit gets stretched to fill the whole frame
    just because it happens to be the deepest thing in its project --
    compute_scale has no concept of "this pit is only a few inches deep
    in absolute terms", only "this pit is the deepest one here". At a
    shared fixed scale, a shallow pit's column is simply short, with
    real blank space below it, the same way a shallow pit already draws
    shorter than a deep one *within* a multi-pit project -- this just
    extends that same relative-depth honesty to a project's single
    deepest pit too, rather than always zooming it to fill the page."""
    if max_depth_in <= 0:
        return 0.0
    if float(max_depth_in) * fixed_scale <= frame_height:
        return fixed_scale
    return compute_scale(max_depth_in, frame_height)


def y_at_depth(frame_top: float, scale: float, depth_in: Decimal) -> float:
    """Page y-coordinate for a given real depth below grade.

    matplotlib's y-axis increases upward (like a graph), but "depth"
    naturally increases downward (like digging a hole), so this is the
    one place that flips that around: it starts at the page position of
    ground level (frame_top) and *subtracts* as depth increases, so a
    bigger depth_in produces a smaller (further down the page) y value.
    """
    return frame_top - float(depth_in) * scale


def band_y_range(frame_top: float, scale: float, cum_before: Decimal, cum_after: Decimal) -> tuple[float, float]:
    """Return (y_top, y_bottom) in page inches for a layer spanning [cum_before, cum_after].

    cum_before/cum_after are the *cumulative* depth from ground level to
    the top and bottom of one soil layer (not that layer's own
    thickness) -- e.g. a second layer that starts 10" down and is 20"
    thick would be called with cum_before=10, cum_after=30. Just runs
    y_at_depth on each end and hands back both page-y coordinates as a
    pair, ready to draw a rectangle between them.
    """
    return y_at_depth(frame_top, scale, cum_before), y_at_depth(frame_top, scale, cum_after)
