import pytest

from tp_drawer.description_layout import (
    DescriptionUnit,
    _classify,
    _place_at_fontsize,
    _push_down,
    _wrap_unit,
    line_height_in,
    place_descriptions,
    scaled_wrap_width,
)

MIN_GAP_RATIO = 0.6
PADDING_RATIO = 0.4
DEFAULT_FONTSIZE = 6.5
ONE_LINE = line_height_in(DEFAULT_FONTSIZE)  # height of a single-line (header-only) block
MIN_GAP = MIN_GAP_RATIO * ONE_LINE
PADDING = PADDING_RATIO * ONE_LINE


def _default(units, wrap_width=30, frame_top=10.0):
    """The push-down-only state, as computed by _place_at_fontsize with an
    unreachable frame_bottom so push-up never engages."""
    return _place_at_fontsize(units, wrap_width, frame_top, -1e9, MIN_GAP_RATIO, PADDING_RATIO, DEFAULT_FONTSIZE)


def test_sufficient_space_uses_the_real_ceiling_not_the_predecessors_landing():
    # unit0 has a huge slot relative to its 1-line text, so its landing sits
    # far below where its text actually ends. unit1 must be free to sit at
    # its own natural top-anchor (not artificially capped near unit0's low
    # landing) since unit0's actual text leaves it plenty of room.
    units = [
        DescriptionUnit(slot_top=10, slot_bot=8, name="A", description=""),
        DescriptionUnit(slot_top=8, slot_bot=6, name="B", description=""),
        DescriptionUnit(slot_top=6, slot_bot=4, name="C", description="", is_last=True),
    ]
    placed = _default(units)

    assert placed[1].block_top_y == pytest.approx(units[1].slot_top - PADDING)  # exactly its own anchor
    assert placed[1].landing_y == pytest.approx(6)
    assert placed[1].connector == "neutral"


def test_genuine_crowding_from_a_long_description_still_cascades():
    frame_top = 10.0
    long_description = "x" * 100  # wraps to exactly 10 lines at width=10
    units = [
        DescriptionUnit(slot_top=frame_top, slot_bot=9.9, name="A", description=long_description),
        DescriptionUnit(slot_top=9.9, slot_bot=0.0, name="B", description="", is_last=True),
    ]
    placed = _default(units, wrap_width=10, frame_top=frame_top)

    height0 = 11 * ONE_LINE  # header + 10 wrapped lines
    expected_block_top0 = frame_top - MIN_GAP
    expected_landing0 = expected_block_top0 - PADDING - height0
    assert placed[0].block_top_y == pytest.approx(expected_block_top0)
    assert placed[0].landing_y == pytest.approx(expected_landing0)
    assert placed[0].connector == "down"

    expected_block_top1 = expected_landing0 - MIN_GAP  # genuinely crowded off its own slot_top
    assert placed[1].block_top_y == pytest.approx(expected_block_top1)
    assert placed[1].connector == "flat"  # its own landing never left slot_bot (0.0) -- tons of room below


def test_push_up_shifts_by_only_the_deficit_not_the_full_available_slack():
    # Direct test of the core push-up fix: B has generous slack (short text,
    # roomy slot) above a thin, genuinely-crowded C -- there's over an inch
    # of headroom between B's real text end and C's natural position, but
    # C only needs a hundredth of an inch to clear frame_bottom. A "pack as
    # tight as possible" approach would use all of that headroom (cramming
    # C's text up against B's); the fix should use only the sliver it needs.
    frame_top = 10.0
    units = [
        DescriptionUnit(slot_top=frame_top, slot_bot=8.0, name="B", description=""),
        DescriptionUnit(slot_top=8.0, slot_bot=7.95, name="C", description="", is_last=True),
    ]
    heights = [ONE_LINE, ONE_LINE]
    unrelieved = _default(units, frame_top=frame_top)
    _, _, unrelieved_text_bottoms = _push_down(units, heights, frame_top, MIN_GAP, PADDING)

    small_rise = 0.01  # tiny compared to the available headroom (over 1.7in -- see below)
    frame_bottom = unrelieved[1].landing_y + small_rise
    placed = _place_at_fontsize(units, 30, frame_top, frame_bottom, MIN_GAP_RATIO, PADDING_RATIO, DEFAULT_FONTSIZE)

    # C's block rose by exactly the deficit -- not by the ~1.72in of real
    # headroom available above it (confirmed separately below).
    assert placed[1].block_top_y - unrelieved[1].block_top_y == pytest.approx(small_rise)
    full_headroom = unrelieved_text_bottoms[0] - MIN_GAP - unrelieved[1].block_top_y
    assert full_headroom > 1.5  # sanity check: plenty of slack was available and NOT used
    assert placed[1].block_top_y < unrelieved_text_bottoms[0] - MIN_GAP - full_headroom / 2  # nowhere near it

    # Only a sliver was needed, so C is still only partially relieved --
    # its connector still reads "down", not "flat" -- proving push-up
    # didn't overshoot into full compaction to get there.
    assert placed[1].connector == "down"

    # B's own text block never moves -- it wasn't part of the shift at all.
    assert placed[0].block_top_y == pytest.approx(unrelieved[0].block_top_y)
    # B's landing does nudge up slightly, though -- just enough to stay
    # min_gap clear of C's (now slightly higher) block, same mechanism
    # that closes the gap for any predecessor whose slack got borrowed.
    assert placed[0].landing_y > units[0].slot_bot
    assert placed[0].landing_y == pytest.approx(placed[1].block_top_y + MIN_GAP)


def test_cascade_stops_once_the_deficit_is_covered_even_with_more_units_to_reach():
    # The cascade walks junction by junction (C<->B, then B<->A), compounding
    # contributions -- but only for as many junctions as the remaining
    # deficit still needs, and only where a junction actually has headroom
    # to give. Here, C alone has real headroom (B's actual text ends well
    # above C's natural spot) -- but the B<->A junction right behind it has
    # none (B is already jammed against A's ceiling). Demanding more than C
    # alone can supply forces the cascade to also try the B<->A junction; it
    # correctly finds nothing there and stops, without ever touching A's own
    # block/landing (unit index 0 is structurally exempt from ever moving,
    # regardless of its is_first flag -- see _pull_up_slack's docstring).
    frame_top = 10.0
    units = [
        DescriptionUnit(slot_top=10.0, slot_bot=8.0, name="A", description=""),
        DescriptionUnit(slot_top=9.9, slot_bot=8.5, name="B", description=""),
        DescriptionUnit(slot_top=9.0, slot_bot=9.4, name="C", description="", is_last=True),
    ]
    heights = [ONE_LINE, ONE_LINE, ONE_LINE]
    block_tops, landings, text_bottoms = _push_down(units, heights, frame_top, MIN_GAP, PADDING)

    headroom_c_alone = text_bottoms[1] - MIN_GAP - block_tops[2]
    headroom_b_and_a = text_bottoms[0] - MIN_GAP - block_tops[1]
    assert headroom_c_alone > 0.4  # C alone genuinely has room to give
    assert headroom_b_and_a == pytest.approx(0.0)  # the next junction back adds nothing
    unrelieved_a_connector = _classify(landings[0], units[0].slot_bot, units[0].is_last)

    # Demand more than even C alone (the best option) can fully supply, so
    # push-up is only ever partially successful here -- the point is which
    # partial result it settles for, not full resolution.
    cap = units[2].slot_bot - landings[2]
    frame_bottom = landings[2] + cap
    placed = _place_at_fontsize(units, 30, frame_top, frame_bottom, MIN_GAP_RATIO, PADDING_RATIO, DEFAULT_FONTSIZE)

    assert placed[2].landing_y == pytest.approx(landings[2] + headroom_c_alone)  # C alone's contribution, not less
    # A's block/landing are IDENTICAL to _push_down's own output -- push-up
    # reached the B<->A junction (found nothing) but never touched A itself.
    # (A's connector is "up", not "neutral": _push_down's own retroactive
    # catch-up already raised it, independent of push-up entirely -- B's
    # block here is genuinely ceiling-constrained against A's real text
    # (that's exactly what headroom_b_and_a == 0 confirms), so A's landing
    # was pulled up to meet it during the push-down pass, before push-up
    # ever runs. What this test demonstrates is that push-up adds nothing
    # further on top of that.)
    assert placed[0].block_top_y == pytest.approx(block_tops[0])
    assert placed[0].landing_y == pytest.approx(landings[0])
    assert placed[0].connector == unrelieved_a_connector


def test_unit_zero_never_rises_even_with_real_frame_headroom():
    # frame_top sits ABOVE unit0's own slot_top here (mirroring production,
    # where FIGURE_TOP_Y is deliberately above FRAME_TOP_Y, the grade
    # line) -- unlike every other unit, unit0's *block* must never rise to
    # use that headroom, or its text would run above grade level.
    frame_top = 10.2
    units = [
        DescriptionUnit(slot_top=10.0, slot_bot=9.0, name="A", description="", is_first=True),
        DescriptionUnit(slot_top=9.0, slot_bot=8.98, name="B", description=""),
        DescriptionUnit(slot_top=8.98, slot_bot=8.96, name="C", description="", is_last=True),
    ]
    heights = [ONE_LINE, ONE_LINE, ONE_LINE]
    unrelieved = _default(units, frame_top=frame_top)
    assert unrelieved[0].connector == "neutral"

    block_tops, landings, text_bottoms = _push_down(units, heights, frame_top, MIN_GAP, PADDING)
    # A never shifts (is_first), so the only reachable group is B+C,
    # seeded from A's own real, unmoved text-bottom.
    headroom = text_bottoms[0] - MIN_GAP - block_tops[1]
    cap = units[2].slot_bot - landings[2]  # C's landing can rise no further than its own neutral cap
    assert headroom > cap  # plenty of room -- the cap, not headroom, is the limiting factor

    frame_bottom = landings[2] + cap + 0.01  # demand slightly more than push-up can ever deliver here
    placed = _place_at_fontsize(units, 30, frame_top, frame_bottom, MIN_GAP_RATIO, PADDING_RATIO, DEFAULT_FONTSIZE)

    # unit0's block never rises -- stays exactly at its own natural
    # top-anchor, never reaching up toward frame_top.
    assert placed[0].block_top_y == pytest.approx(block_tops[0])
    assert placed[0].block_top_y < frame_top
    # Its landing, however, does get pulled up -- B+C's shift was seeded
    # from A's real text-bottom, so A's landing (which had slack below
    # that text) is pulled up to close the gap, same as any predecessor
    # whose slack got borrowed. This is a different concern from the
    # block-never-rises rule above, not a violation of it.
    assert placed[0].landing_y > units[0].slot_bot
    assert placed[0].connector == "up"


def test_last_unit_continues_the_chain_once_relieved():
    # A has generous slack; B and C are both thin, tightly clustered close
    # to A. Regression test for a real bug: once B is genuinely relieved
    # (pushed up), C's *text block* must rise to sit properly min_gap below
    # B's new landing rather than staying stranded at its own natural
    # top-anchor -- but C's *landing* (the connector tick) is never allowed
    # to rise above its own neutral slot_bot, since nothing sits below C
    # for an "up" connector to mean anything. So C's connector reads
    # "flat" here, not "up", even though its text has visibly moved.
    frame_top = 10.0
    units = [
        DescriptionUnit(slot_top=frame_top, slot_bot=9.0, name="A", description=""),
        DescriptionUnit(slot_top=9.0, slot_bot=8.98, name="B", description=""),
        DescriptionUnit(slot_top=8.98, slot_bot=8.96, name="C", description="", is_last=True),
    ]
    heights = [ONE_LINE, ONE_LINE, ONE_LINE]
    unrelieved = _default(units, frame_top=frame_top)
    assert unrelieved[1].connector == "down"  # B genuinely needs help
    assert unrelieved[2].connector == "down"  # C is crowded too, by B's overflow cascading onto it

    block_tops, landings, text_bottoms = _push_down(units, heights, frame_top, MIN_GAP, PADDING)
    cap = units[2].slot_bot - landings[2]  # C's landing can rise no further than its own neutral cap
    frame_bottom = landings[2] + cap  # exactly enough to fully relieve C, no more

    placed = _place_at_fontsize(units, 30, frame_top, frame_bottom, MIN_GAP_RATIO, PADDING_RATIO, DEFAULT_FONTSIZE)

    assert placed[1].connector == "up"  # B was genuinely relieved
    assert placed[2].connector == "flat"  # C's landing stays pinned at neutral -- never "up"
    assert placed[2].landing_y == pytest.approx(units[2].slot_bot)
    # C's text block still properly continues the chain -- exactly min_gap below B's landing.
    assert placed[1].landing_y - placed[2].block_top_y == pytest.approx(MIN_GAP)


def test_predecessors_landing_tracks_the_pushed_units_actual_block_top():
    # B has genuine slack (short text, roomy slot) but doesn't itself
    # overflow, so push-down alone leaves it neutral. C (last, a thin slot)
    # overflows just enough that shifting it alone up to its own neutral cap
    # needs real lift above where push-down left it. C's *landing* stays
    # pinned at its own neutral slot_bot (nothing sits below it for an "up"
    # connector to mean anything), but C's *text block* still rises to
    # continue the chain -- so B's landing tracks that risen block_top, a
    # clean min_gap above it, without needing to reach all the way up to
    # where B's own text actually ends (there was more slack available than
    # the deficit needed).
    frame_top = 10.0
    units = [
        DescriptionUnit(slot_top=frame_top, slot_bot=9.5, name="A", description="", is_first=True),
        DescriptionUnit(slot_top=9.5, slot_bot=9.0, name="B", description=""),
        DescriptionUnit(slot_top=9.0, slot_bot=8.9, name="C", description="", is_last=True),
    ]
    heights = [ONE_LINE, ONE_LINE, ONE_LINE]
    block_tops, landings, text_bottoms = _push_down(units, heights, frame_top, MIN_GAP, PADDING)
    unrelieved = _default(units, frame_top=frame_top)
    assert unrelieved[1].connector == "neutral"  # B has slack but doesn't need to use it yet
    assert unrelieved[2].connector == "down"  # C genuinely overflows its own tiny slot

    cap = units[2].slot_bot - landings[2]
    frame_bottom = landings[2] + cap  # exactly enough to fully relieve C, no more
    placed = _place_at_fontsize(units, 30, frame_top, frame_bottom, MIN_GAP_RATIO, PADDING_RATIO, DEFAULT_FONTSIZE)

    assert placed[2].connector == "flat"  # C's landing stays pinned at neutral -- never "up"
    assert placed[2].landing_y == pytest.approx(units[2].slot_bot)

    # B's landing tracks C's actual (risen) block_top, a clean min_gap above it.
    assert placed[1].connector == "up"
    assert placed[1].landing_y == pytest.approx(placed[2].block_top_y + MIN_GAP)
    assert placed[1].block_top_y == pytest.approx(unrelieved[1].block_top_y)  # B's own text block never moves
    # B's landing falls well short of B's own real text-bottom -- proof
    # the shift only used the slack it needed, not all of it.
    assert placed[1].landing_y < text_bottoms[1]

    # No collision: C's (now elevated) block clears B's (now raised) landing by exactly min_gap.
    assert placed[1].landing_y - placed[2].block_top_y == pytest.approx(MIN_GAP)

    # A (is_first) is untouched -- it isn't even the winning group's
    # immediate predecessor (that's B), so nothing pulls it either.
    assert placed[0].block_top_y == pytest.approx(block_tops[0])
    assert placed[0].landing_y == pytest.approx(landings[0])


def test_predecessor_with_no_slack_is_never_flattened_by_a_neighbours_shift():
    # Regression test for a real, fixed bug: the push-up cascade's last
    # step used to pull a predecessor's landing up to its own slot_bot
    # unconditionally, whenever the group below it moved -- even when that
    # predecessor had NO slack of its own (its own text already overflows
    # its own slot, so its landing correctly tracks its own text_bottom,
    # below slot_bot). Forcing it up to slot_bot in that case silently
    # turned a correct "down" connector into an incorrect "flat" one, with
    # the landing left floating above where the predecessor's own text
    # actually ends.
    frame_top = 10.0
    units = [
        DescriptionUnit(slot_top=frame_top, slot_bot=9.5, name="A", description="", is_first=True),
        DescriptionUnit(slot_top=9.5, slot_bot=9.3, name="B", description="word " * 12),
        DescriptionUnit(slot_top=8.5, slot_bot=8.3, name="C", description="", is_last=True),
    ]
    heights = [len(_wrap_unit(u, 30)) * ONE_LINE for u in units]
    block_tops, landings, text_bottoms = _push_down(units, heights, frame_top, MIN_GAP, PADDING)

    # Confirm the scenario: B genuinely overflows its own slot (no slack),
    # and C (last) has real headroom above it -- entirely independent of
    # B's own overflow, since C's slot starts well below where B's text ends.
    assert text_bottoms[1] == pytest.approx(landings[1])  # B has no slack
    assert landings[1] < units[1].slot_bot
    headroom_b_to_c = text_bottoms[1] - MIN_GAP - block_tops[2]
    cap = units[2].slot_bot - landings[2]  # C's landing can rise no further than its own neutral cap
    assert headroom_b_to_c > 0
    assert cap > 0

    # Demand only a small lift -- well within both what the B<->C junction
    # alone can supply AND C's own neutral cap -- so the cascade never
    # needs to touch B itself, and the cap isn't what limits the result.
    small_lift = 0.3 * min(headroom_b_to_c, cap)
    assert small_lift < headroom_b_to_c
    assert small_lift < cap
    frame_bottom = landings[2] + small_lift
    placed = _place_at_fontsize(units, 30, frame_top, frame_bottom, MIN_GAP_RATIO, PADDING_RATIO, DEFAULT_FONTSIZE)

    assert placed[2].landing_y == pytest.approx(frame_bottom)  # C is fully relieved
    # B must be completely untouched -- same landing, same "down" connector.
    assert placed[1].landing_y == pytest.approx(landings[1])
    assert placed[1].connector == "down"


def test_cascade_compounds_multiple_junctions_instead_of_picking_one():
    # Regression test for a real, fixed bug (and the exact behaviour a user
    # reported as "push-up takes more space than needed"): the push-up step
    # used to search for a single best rigid group and use ONLY that one
    # junction's headroom, discarding a nearer, smaller pocket of headroom
    # entirely whenever a further-back junction offered more on its own.
    # That could both (a) fail to reach a target the combined slack could
    # easily have supplied, needlessly triggering font-shrink, and (b) shove
    # an in-between unit by the FULL amount taken from a distant junction
    # when only a fraction of it was actually required from that unit.
    #
    # Here, D (last) needs more lift than the nearest junction (C<->D) can
    # give alone, but less than the nearest two junctions (C<->D and B<->C)
    # combined can give.
    frame_top = 10.0
    units = [
        DescriptionUnit(slot_top=frame_top, slot_bot=9.5, name="A", description="", is_first=True),
        DescriptionUnit(slot_top=9.5, slot_bot=9.2, name="B", description="word " * 6),
        DescriptionUnit(slot_top=9.0, slot_bot=8.6, name="C", description=""),
        DescriptionUnit(slot_top=8.6, slot_bot=8.3, name="D", description="word " * 24, is_last=True),
    ]
    heights = [len(_wrap_unit(u, 30)) * ONE_LINE for u in units]
    block_tops, landings, text_bottoms = _push_down(units, heights, frame_top, MIN_GAP, PADDING)

    headroom_c_to_d = text_bottoms[2] - MIN_GAP - block_tops[3]
    headroom_b_to_c = text_bottoms[1] - MIN_GAP - block_tops[2]
    assert headroom_c_to_d > 0
    assert headroom_b_to_c > 0

    # A target only the two junctions COMBINED can reach.
    needed = headroom_c_to_d + 0.6 * headroom_b_to_c
    assert needed > max(headroom_c_to_d, headroom_b_to_c)  # neither junction alone would suffice
    cap = units[3].slot_bot - landings[3]
    assert needed < cap  # confirm the last unit's own neutral cap isn't the limiting factor here
    frame_bottom = landings[3] + needed

    placed = _place_at_fontsize(units, 30, frame_top, frame_bottom, MIN_GAP_RATIO, PADDING_RATIO, DEFAULT_FONTSIZE)

    # D reaches the full target -- something a single-best-junction search
    # (capped at max(headroom_c_to_d, headroom_b_to_c)) could never do.
    assert placed[3].landing_y == pytest.approx(frame_bottom)

    # C -- the in-between unit -- has its own slack (its landing sits at its
    # own slot_bot while its text ends higher up), which is *why*
    # headroom_c_to_d was available in the first place: the C<->D junction's
    # contribution fully uses that slack, so C's landing catches up to its
    # own real text_bottom right there (same rule _push_down applies, see
    # _pull_up_slack's docstring) -- independent of, and before, the B<->C
    # junction's own separate contribution to C.
    catchup_from_c_to_d = text_bottoms[2] - landings[2]
    assert catchup_from_c_to_d > 0  # confirms C's slack is what made headroom_c_to_d possible
    # C's *total* movement is that catch-up plus only the fraction of the
    # B<->C junction's headroom actually needed (0.6 of it here) -- not the
    # whole junction's capacity and not the full deficit: the
    # minimum-disruption fix.
    c_shift = placed[2].landing_y - landings[2]
    assert c_shift == pytest.approx(catchup_from_c_to_d + 0.6 * headroom_b_to_c)
    assert c_shift < catchup_from_c_to_d + headroom_b_to_c


def test_last_unit_can_still_be_pushed_down_by_its_own_overflow():
    # The clamp only forbids the last unit from rising above neutral -- it
    # must still be able to go "down" when its own text genuinely overflows
    # its own slot, independent of any push-up event.
    units = [
        DescriptionUnit(slot_top=10.0, slot_bot=9.95, name="A", description="x" * 60, is_last=True),
    ]
    placed = _default(units)
    assert placed[0].connector == "down"
    assert placed[0].landing_y < units[0].slot_bot


def test_push_up_can_carry_a_non_last_units_text_above_its_own_boundary():
    # Same crowded A/B/C cluster as the chain-continuity test above, viewed
    # from a different angle: once relieved, B's text doesn't just move --
    # it rises clear above B's own unit's true upper boundary (slot_top).
    # That's exactly what makes a diagonal ("up") connector necessary: the
    # text no longer sits anywhere near the depth it describes.
    frame_top = 10.0
    units = [
        DescriptionUnit(slot_top=frame_top, slot_bot=9.0, name="A", description=""),
        DescriptionUnit(slot_top=9.0, slot_bot=8.98, name="B", description=""),
        DescriptionUnit(slot_top=8.98, slot_bot=8.96, name="C", description="", is_last=True),
    ]
    heights = [ONE_LINE, ONE_LINE, ONE_LINE]
    block_tops, landings, text_bottoms = _push_down(units, heights, frame_top, MIN_GAP, PADDING)
    unrelieved = _default(units, frame_top=frame_top)
    assert unrelieved[1].connector == "down"  # confirms B genuinely needs help

    cap = units[2].slot_bot - landings[2]
    frame_bottom = landings[2] + cap
    placed = _place_at_fontsize(units, 30, frame_top, frame_bottom, MIN_GAP_RATIO, PADDING_RATIO, DEFAULT_FONTSIZE)

    assert placed[1].connector == "up"
    assert placed[1].block_top_y > units[1].slot_top  # B's text rises above its own unit's true upper boundary
    # C (last) is part of the same shifted group as B, so its *text* block
    # must still properly continue the chain below B's new position -- but
    # its landing stays pinned at its own neutral slot_bot, since nothing
    # sits below C for an "up" connector to mean.
    assert placed[2].connector == "flat"
    assert placed[2].landing_y == pytest.approx(units[2].slot_bot)
    assert placed[1].landing_y - placed[2].block_top_y == pytest.approx(MIN_GAP)


def test_push_up_cascade_reaches_back_only_as_far_as_needed():
    # D (last, thin) needs lift to reach its neutral cap. C<->D (the nearest
    # junction) has no headroom of its own by default, so the cascade must
    # reach back one more junction, to B<->A, for D to fully recover to
    # neutral.
    frame_top = 10.0
    units = [
        DescriptionUnit(slot_top=frame_top, slot_bot=9.0, name="A", description=""),
        DescriptionUnit(slot_top=9.0, slot_bot=8.98, name="B", description=""),
        DescriptionUnit(slot_top=8.98, slot_bot=8.96, name="C", description=""),
        DescriptionUnit(slot_top=8.96, slot_bot=8.94, name="D", description="", is_last=True),
    ]
    heights = [ONE_LINE] * 4
    block_tops, landings, text_bottoms = _push_down(units, heights, frame_top, MIN_GAP, PADDING)
    headroom_c_alone = text_bottoms[1] - MIN_GAP - block_tops[2]
    assert headroom_c_alone == pytest.approx(0.0)  # confirms C alone can't relieve D at all

    cap = units[3].slot_bot - landings[3]
    frame_bottom = landings[3] + cap  # exactly enough to fully relieve D, no more
    placed = place_descriptions(
        units, frame_top=frame_top, frame_bottom=frame_bottom,
        min_gap_ratio=MIN_GAP_RATIO, padding_ratio=PADDING_RATIO, fontsize_default=DEFAULT_FONTSIZE,
    )

    # D (last) properly continues the chain below C once relieved -- its
    # text block rises with the shift -- but its landing stays pinned at
    # its own neutral slot_bot, since nothing sits below D for an "up"
    # connector to mean anything.
    assert placed[3].connector == "flat"
    assert placed[3].landing_y == pytest.approx(units[3].slot_bot)
    assert placed[2].landing_y - placed[3].block_top_y == pytest.approx(MIN_GAP)
    assert placed[1].connector == "up"  # B was reached too, not just C
    # A's slack (the gap between where its text actually ends and its own
    # slot_bot) is exactly what seeded B's shift -- A's landing rises to
    # close that gap (else B's block would clip through A's landing line),
    # even though A's own text block never moves.
    assert placed[0].connector == "up"
    assert placed[0].block_top_y == pytest.approx(block_tops[0])
    assert placed[1].block_top_y != pytest.approx(block_tops[1])


def test_shrinking_has_no_fixed_floor_even_with_many_verbose_units():
    # A pathological number of units with long descriptions crammed into a
    # tiny frame -- gaps and text both scale with font size, so this must
    # still resolve rather than overflow or hang.
    frame_top = 10.0
    frame_bottom = 9.9  # a sliver of a box
    units = []
    top = frame_top
    for i in range(15):
        bot = top - 0.001  # slivers -- no true-scale room to speak of
        units.append(
            DescriptionUnit(slot_top=top, slot_bot=bot, name=f"Unit{i}", description="Lorem ipsum dolor sit amet consectetur.", is_last=(i == 14))
        )
        top = bot

    placed = place_descriptions(units, frame_top=frame_top, frame_bottom=frame_bottom, min_gap_ratio=MIN_GAP_RATIO, padding_ratio=PADDING_RATIO)

    assert min(p.landing_y for p in placed) >= frame_bottom - 1e-6
    assert placed[0].fontsize < DEFAULT_FONTSIZE


def test_scaled_wrap_width_grows_as_fontsize_shrinks():
    # Character width scales ~linearly with fontsize, so fitting the same
    # page-inch line width at half the fontsize takes ~double the characters.
    assert scaled_wrap_width(30, 6.5, 6.5) == 30  # no shrink -> unchanged
    assert scaled_wrap_width(30, 6.5, 3.25) == 60  # half the fontsize -> double the characters
    assert scaled_wrap_width(30, 6.5, 0.5) >= 1  # never collapses to zero/negative


def test_wrap_width_rescales_with_fontsize_to_keep_visual_width_stable():
    # Keeping the character-count wrap width fixed across shrink steps would
    # make shrunk text visibly *narrower* than default-size text (the same
    # character count, rendered smaller, spans less page-inch width). So the
    # wrap width is instead rescaled at half fontsize -- rewrapping to
    # roughly double the characters per line -- and the rendered width
    # (characters * fontsize) of the longest body line lands in the same
    # ballpark either way, instead of shrinking along with the font.
    description = (
        "Heterogeneous fill material comprising brick fragments, gravel, sand, and organic debris "
        "throughout, with occasional cobbles and construction rubble noted at varying depths."
    )
    unit = DescriptionUnit(slot_top=10.0, slot_bot=9.9, name="Fill", description=description, is_last=True)

    default_lines = _wrap_unit(unit, 30)
    half_fontsize = DEFAULT_FONTSIZE / 2
    half_wrap_width = scaled_wrap_width(30, DEFAULT_FONTSIZE, half_fontsize)
    assert half_wrap_width == 60
    half_lines = _wrap_unit(unit, half_wrap_width)

    assert len(half_lines) < len(default_lines)  # roughly half as many lines, not the same wrapping
    default_width = max(len(line) for line in default_lines[1:]) * DEFAULT_FONTSIZE
    half_width = max(len(line) for line in half_lines[1:]) * half_fontsize
    assert half_width == pytest.approx(default_width, rel=0.3)

    # Wired into the actual shrink loop, not just the standalone formula: a
    # modest shrink still rewraps (differently) rather than reusing the
    # default-size lines, and matches what scaled_wrap_width predicts.
    units = [unit]
    roomy = place_descriptions(units, frame_top=10.0, frame_bottom=0.0, wrap_width=30, min_gap_ratio=MIN_GAP_RATIO, padding_ratio=PADDING_RATIO)
    cramped = place_descriptions(units, frame_top=10.0, frame_bottom=9.85, wrap_width=30, min_gap_ratio=MIN_GAP_RATIO, padding_ratio=PADDING_RATIO)
    assert cramped[0].fontsize < roomy[0].fontsize  # shrink actually engaged
    assert cramped[0].lines != roomy[0].lines
    expected_width = scaled_wrap_width(30, DEFAULT_FONTSIZE, cramped[0].fontsize)
    assert cramped[0].lines == _wrap_unit(unit, expected_width)


def test_returns_empty_for_no_units():
    assert place_descriptions([], frame_top=10, frame_bottom=0) == []
