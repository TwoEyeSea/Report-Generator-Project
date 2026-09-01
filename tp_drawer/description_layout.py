"""Pure layout math for the self-reflowing unit-description stack.

Each subsurface unit's description is an independently-sized text block,
stacked top-to-bottom in depth order to the right of the stratigraphy
column. By default, a block is top-anchored just under its own unit's upper
boundary (`slot_top`), independent of how tall the text is; its landing (the
tick a connector attaches to) independently defaults to the unit's lower
boundary (`slot_bot`). When there's sufficient space these never interact --
the block simply has extra clearance above its landing, and the connector is
a plain flat tick.

Crowding is always measured against where the text *above* a unit actually
ends (not against that unit's landing, which may sit far below its own text
when there's slack) -- otherwise a unit with a big unused gap would never
let anything below it benefit from that space.

Overflow (the block's natural text is taller than the unit's own true
thickness) is resolved in priority order:
  1. Push down -- a unit's own block is capped by the ceiling from the text
     above it; if that pushes its text past its own slot_bot, the landing
     is dragged down too, cascading through subsequent units.
  2. Push up -- only attempted once the cascade would carry the deepest
     (last unit's) landing past the bottom of the drawing's frame, and even
     then only by exactly the amount needed to bring that landing back up
     to the frame boundary -- never further, and never further than the
     last unit's own neutral slot_bot (nothing sits below it for an "up"
     connector to meaningfully point at, so its landing's two faces are
     always just flat/neutral or down; only its *text block* is free to
     keep rising to continue the chain past that clamp). A shrinking suffix
     search finds the smallest run of units, starting nearest the overflow,
     with enough headroom above them (space between where they currently
     sit and whatever text is directly above them) to absorb that exact
     shift; the whole run is then translated upward by that single amount,
     rigidly, so every gap it already had -- above its own natural
     top-anchor, or between neighbours -- is preserved untouched rather
     than being squeezed down to the bare minimum gap. This is deliberate:
     a unit only donates as much of its slack as the deficit actually
     needs, never all of it, so a relieved unit's text never ends up
     crammed flush against the text above it when a smaller nudge would
     have done the job. The shift can still carry a unit's text above its
     own unit's true upper boundary when the deficit demands it -- the
     diagonal connector is exactly what reconciles "text sitting here" with
     "depth it actually describes". The first unit's *block* is exempt from
     shifting at all: its ceiling is the frame itself (frame_top) rather
     than a preceding unit's text, and frame_top sits deliberately above
     the grade line for other purposes, so letting it rise would run its
     text above ground level, which must never happen -- its block always
     stays at its own natural top-anchored position, and the search for
     headroom stops there, using its real (unmoved) text-bottom as the
     fixed ceiling for whatever's shifting below it. Its *landing* is a
     separate matter, exactly mirroring the last unit's block/landing
     split (just mirrored top-for-bottom): if the group shifting below it
     rises into the gap between the first unit's real text-bottom and its
     own (possibly slack-capped) landing, that landing gets pulled up too
     -- same as any other predecessor whose slack the shift used (see
     below) -- so it never sits stranded underneath the shifted block it's
     supposedly still above. Both the first and last unit can still be
     pushed down if genuinely crowded -- only the upward direction is
     restricted, and only for these two units' blocks specifically. Whichever
     suffix ends up shifting, the unit immediately above it (whose headroom
     the shift used) has its own landing pulled up to match the shifted
     suffix's new top -- closing the gap so nothing below it renders past
     a landing line that's no longer where the nearest text actually
     starts.
  3. Shrink the font and start over -- smaller text (and proportionally
     smaller gaps) may fit several units "neatly" that didn't before, so
     this is a full reset, not a patch. Because gaps shrink with the font
     too, there's no fixed floor: some small enough font always fits. The
     character-count wrap width is rescaled at every fontsize tried (see
     _scaled_wrap_width) so a line always spans roughly the same page-inch
     width regardless of fontsize -- a smaller font fits proportionally
     more characters per line, so wrapped lines do change as the font
     shrinks (never identical to the default-size wrapping), but the
     *number* of lines a description wraps to can only ever go down (or
     stay the same) as the wrap width grows, so height still shrinks
     monotonically with fontsize -- no oscillation, no fixed floor.

No matplotlib imports here so this stays trivially unit-testable, mirroring
layout.py.

PLAIN-ENGLISH SUMMARY FOR THE ALGORITHM ABOVE (read this first, then the
detailed rules above will make more sense):
Picture a bookshelf where each shelf (a soil unit) wants its own label
sitting right next to it. If a label's text is short, no problem -- it
fits neatly beside its shelf. But if a label is a long paragraph, it
might be taller than its own shelf and start overlapping the label
below it. This module's job is to slide labels up and down to avoid
that overlap, doing the *least* disruptive thing first, and only
escalating to something more drastic if it has to:
  1. First, just nudge a too-tall label's neighbours *down* out of its
     way (like adding a line break before the next item on a to-do list).
  2. If nudging everything down would run the last label off the bottom
     of the page, instead try scooting a whole cluster of labels *up*
     together -- but only as far as needed to clear the bottom, like
     sliding a stack of books up a shelf just far enough to close the
     gap at the end, not jamming them all the way together.
  3. If even that doesn't leave enough room, shrink the font size for
     *all* the labels and start over from scratch -- smaller text takes
     less vertical space, so this always eventually fits.
Each unit's connecting line ("connector") then gets drawn flat, sloping
down, or sloping up, depending on how far its label ended up moving away
from its "natural" position next to its own shelf.
"""

import textwrap
from dataclasses import dataclass

LINE_HEIGHT_FACTOR = 1.4  # single-spaced line height as a multiple of font point size
SHRINK_FACTOR = 0.9  # multiplicative font-size step while searching for a fit
FONTSIZE_FLOOR = 0.01  # technical safety bound only (avoids unbounded iteration), not a design floor -- see module docstring


# ADVANCED TECHNIQUE -- @dataclass(frozen=True):
# This is the same @dataclass auto-generates-an-__init__-for-you trick
# used throughout the project (see models.py for the fuller explanation),
# but with frozen=True added. A "frozen" dataclass refuses to let you
# change a field after it's created -- `unit.slot_top = 5` would raise an
# error instead of silently succeeding. That's deliberate here: these
# objects represent a fixed snapshot of "where this unit's text/depth
# markers are" at one specific point in the layout calculation, and the
# functions below build a *new* object with updated numbers rather than
# mutating an old one in place. That makes the flow of data through this
# file easier to reason about -- if you're holding a DescriptionUnit, you
# know for certain nothing else in the program can have changed its
# values behind your back.
@dataclass(frozen=True)
class DescriptionUnit:
    """One soil unit's raw input to the layout algorithm: where it
    "naturally" sits (slot_top/slot_bot, straight from the true-to-scale
    column) plus the name/description text that needs to fit somewhere
    near there."""

    slot_top: float
    slot_bot: float
    name: str
    description: str
    is_last: bool = False
    is_first: bool = False


@dataclass(frozen=True)
class PlacedDescription:
    """One soil unit's final, computed layout result: exactly where its
    text block and landing tick ended up after all the push-down/push-up/
    shrink logic below has run, ready for drawing.py to draw as-is with
    no further decisions to make."""

    landing_y: float
    block_top_y: float
    connector: str  # "neutral" | "down" | "up" | "flat"
    lines: list[str]
    fontsize: float


def line_height_in(fontsize: float) -> float:
    """Single-spaced line height in page inches -- exposed so the renderer
    can stack the wrapped lines it draws at the same spacing this module
    used to compute block heights.

    Font sizes are conventionally measured in "points", and by a
    long-standing print convention, 72 points = 1 inch -- that's where
    the /72.0 comes from, converting a point-based fontsize into
    page-inches. LINE_HEIGHT_FACTOR (1.4) then adds normal single-spaced
    line spacing on top -- if lines were stacked at exactly the font's
    raw height with no factor, tall letters like "g" or "j" on one line
    would nearly touch the line below."""
    return fontsize * LINE_HEIGHT_FACTOR / 72.0


def _wrap_unit(unit: DescriptionUnit, wrap_width: int) -> list[str]:
    """Turn one unit's name + description into the exact list of text
    lines that will be drawn, e.g. ["CLAY", "Soft, grey, silty clay", "with
    occasional shell fragments."] -- the name always gets its own line
    (as a header), and textwrap.wrap breaks the description into lines no
    wider than wrap_width characters, breaking only at word boundaries
    (so it never cuts a word in half)."""
    header = [unit.name.upper()]
    body = textwrap.wrap(unit.description, width=wrap_width) if unit.description else []
    return header + body


def _scaled_wrap_width(wrap_width: int, fontsize_default: float, fontsize: float) -> int:
    """Character-count wrap width for a given fontsize, calibrated against
    `wrap_width` at fontsize_default so a wrapped line spans roughly the
    same page-inch width at any fontsize the shrink loop tries -- glyph
    width scales ~linearly with fontsize, so a smaller font needs
    proportionally more characters per line to fill the same physical
    width."""
    # max(1, ...) is a safety floor: at an extremely small fontsize the
    # formula below could round down to 0 or a negative number, and
    # textwrap.wrap would either error or behave oddly with a
    # non-positive width -- clamping to at least 1 character keeps it
    # well-defined even in that extreme case.
    return max(1, round(wrap_width * fontsize_default / fontsize))


def _classify(landing_y: float, slot_bot: float, is_last: bool) -> str:
    """Decide how the connector line to this unit's landing should look,
    purely by comparing where the landing *ended up* (landing_y) to where
    it would sit if nothing had to move (slot_bot). Remember page
    y-coordinates increase upward, so "landing_y > slot_bot" means the
    landing was dragged higher up the page than its natural spot (the
    push-up case), and "landing_y < slot_bot" means it was pushed further
    down (the push-down case)."""
    if landing_y > slot_bot:
        return "up"
    if landing_y < slot_bot:
        return "down"
    return "flat" if is_last else "neutral"


def _push_down(
    units: list[DescriptionUnit],
    heights: list[float],
    frame_top: float,
    min_gap: float,
    padding: float,
) -> tuple[list[float], list[float], list[float]]:
    """Step 1 of the algorithm (see the module docstring's plain-English
    summary): walk down the page once, top to bottom, letting any
    too-tall block above shove the next one further down than it would
    otherwise sit. This is a single top-to-bottom pass -- once a unit's
    position is decided it's never revisited in this function -- which is
    why it's called a "cascade": one unit's overflow ripples down into
    the next, like a row of dominoes falling in one direction.

    Forward cascade: each block prefers to start just under its own
    slot_top; if the text above leaves less room than that, it's pushed
    down instead. Ceiling is measured against the actual bottom edge of the
    text above (not that unit's landing, which may sit far lower when it
    has slack) -- a block's own landing stays at slot_bot as long as the
    block, wherever it ended up, doesn't reach past it; only an actual
    overflow past slot_bot drags the landing down too."""
    n = len(units)
    block_tops = [0.0] * n
    landings = [0.0] * n
    text_bottoms = [0.0] * n
    prev_text_bottom = frame_top
    for i, unit in enumerate(units):
        ceiling = prev_text_bottom - min_gap
        block_tops[i] = min(unit.slot_top - padding, ceiling)
        natural_bottom = block_tops[i] - padding - heights[i]
        landings[i] = min(unit.slot_bot, natural_bottom)
        text_bottoms[i] = natural_bottom
        prev_text_bottom = natural_bottom
    return block_tops, landings, text_bottoms


def _pull_up_slack(
    units: list[DescriptionUnit],
    heights: list[float],
    block_tops: list[float],
    landings: list[float],
    text_bottoms: list[float],
    frame_top: float,
    frame_bottom: float,
    min_gap: float,
    padding: float,
) -> None:
    """Step 2 of the algorithm: after step 1 (_push_down) has run and the
    last unit's landing still overflows past the bottom of the frame,
    shift the smallest possible trailing group of units upward by exactly
    the amount needed to bring that landing back to frame_bottom -- no
    more. Modifies block_tops/landings in place (rather than returning new
    lists) to slot its results into the arrays _push_down already built,
    only for the units in the winning group.

    Only called when the push-down cascade has pushed the last unit's
    landing past the frame's bottom edge. (It's always the *last* unit
    that's deepest: push_down's cascade only ever pushes each unit's
    landing further down than the one above it -- both because each
    unit's own true depth (slot_bot) is deeper than its predecessor's, and
    because a crowded predecessor's overflow only ever pushes a successor
    down, never up -- so the last unit's landing is always the single
    deepest point in the whole stack. Checking only landings[-1] is
    therefore enough; no other unit needs a separate check.)

    THE TARGET -- how far the shift needs to reach:
    The deficit is frame_bottom - landings[-1]. But the last unit's
    landing is never allowed to rise above its own neutral slot_bot (see
    the module docstring) regardless of how much the deficit demands, so
    the actual rise this function will try to deliver is capped at
    whichever is smaller: the deficit itself, or the headroom already
    available between the last landing and its own slot_bot. If that cap
    is already zero or negative (the last unit is already sitting right
    at its own neutral ceiling), push-up has nothing left to give and the
    remaining deficit is left for the font-shrink step to resolve.

    THE SEARCH -- how many units the shift needs to reach back through:
    Try shifting just the last unit first, then the last two, then the
    last three, and so on working back up the page (a classic
    shrink-the-search-space loop). For a candidate group starting at unit
    `start`, its available headroom is the gap between wherever its first
    unit currently sits and whatever text ends directly above it (seeded
    from that predecessor's actual, unmoved text-bottom -- not its
    landing, which may sit lower still if it has its own slack). The
    first candidate whose headroom covers the needed rise wins; reaching
    further back than necessary would move more text than the deficit
    actually requires. If no candidate has enough headroom even after
    reaching all the way back, the largest reachable group absorbs as
    much of the rise as its headroom allows, and the rest is left for
    font-shrink.

    Because the shift is a single rigid translation -- every unit in the
    winning group moves up by exactly the same amount -- every gap that
    group already had (natural top-anchor slack, or generous room between
    neighbours) survives untouched. Only the amount of slack actually
    needed to close the deficit gets used; nothing is compacted down to
    the bare minimum gap the way a "pack as tight as possible" approach
    would, which is what used to leave relieved units crammed flush
    against the text above them even when only a small nudge was needed.

    The first unit is where the search must stop: it never shifts (see
    the module docstring for why), so a group reaching back to it is
    seeded from its own real, unmoved text-bottom, and the search goes no
    further -- there's nothing above it to reach for.

    Whichever group ends up shifting, the unit immediately above it (start
    - 1) was used only as a *seed* -- its own landing/block are left
    untouched here, still sitting wherever _push_down put them. If that
    unit has slack (its landing capped at its own slot_bot while its text
    actually ends higher up), the shifted group was seeded from that
    higher text-bottom, meaning it can legitimately occupy the vertical
    space down to there -- including space below start - 1's own landing
    line. Left alone, that landing line -- and the text-start of whatever
    a future edit adds -- would sit stranded below the top of the shifted
    group, clipping through it. start - 1's landing is therefore pulled up
    to close that gap, floored at its own slot_bot so it's never dragged
    below its own true depth as a side effect of relieving a unit it
    isn't itself part of."""
    n = len(units)
    last = units[-1]
    deficit = frame_bottom - landings[-1]
    needed_rise = min(deficit, last.slot_bot - landings[-1])
    if needed_rise <= 0:
        return  # the last unit is already at its own neutral ceiling -- push-up can't help

    best_start = None
    best_shift = -1.0  # sentinel below any real shift (shifts are always >= 0)
    # range(n - 1, -1, -1) counts backward: n-1, n-2, ..., 1, 0 -- "try
    # shifting just the last unit, then the last two, then the last
    # three, ..." `break` stops at the very first group with enough
    # headroom, so the result is the *smallest* group and the *exact*
    # shift the deficit needs -- never more. A candidate's headroom isn't
    # guaranteed to grow the further back the search reaches (unlike a
    # "pack everything solid" approach, a rigid shift's headroom depends
    # only on the one junction at the front of the group, which can be
    # tighter for an earlier group than a later one) -- so only a
    # candidate that's actually better than the best found so far replaces
    # it; a worse, merely-more-recently-tried one never does.
    for start in range(n - 1, -1, -1):
        unit = units[start]
        if unit.is_first:
            # This unit never shifts -- see the module docstring. If it's
            # also the only unit in the whole stack, there's nothing below
            # it to shift either, and the search ends with nothing found.
            if start == n - 1:
                break
            seed = text_bottoms[start]
            shift_start = start + 1
        else:
            seed = frame_top if start == 0 else text_bottoms[start - 1]
            shift_start = start
        headroom = max(0.0, seed - min_gap - block_tops[shift_start])
        shift = min(needed_rise, headroom)
        if shift > best_shift:
            best_start, best_shift = shift_start, shift
        if headroom >= needed_rise or unit.is_first:
            break  # sufficient, or this was the last possible group to try

    if best_start is None or best_shift <= 0:
        return
    start = best_start
    shift = best_shift
    # ADVANCED TECHNIQUE -- mutating the caller's lists in place:
    # Unlike most functions in this file, _pull_up_slack doesn't return
    # new lists -- it directly edits the block_tops/landings lists that
    # were passed in. That works because Python lists are passed by
    # reference: `block_tops` here is the *same* list object
    # _place_at_fontsize created, not a copy, so changes made to it here
    # are visible back in _place_at_fontsize once this function returns --
    # which is why this function's own return type is `None`; its whole
    # effect is this in-place edit.
    for i in range(start, n):
        block_tops[i] += shift
        landings[i] += shift
    if start > 0:
        landings[start - 1] = max(units[start - 1].slot_bot, block_tops[start] + min_gap)


def _place_at_fontsize(
    units: list[DescriptionUnit],
    wrap_width: int,
    frame_top: float,
    frame_bottom: float,
    min_gap_ratio: float,
    padding_ratio: float,
    fontsize: float,
) -> list[PlacedDescription]:
    """Run steps 1 and 2 of the algorithm once, at one specific fontsize,
    and package the results as a list of PlacedDescription. This is the
    function place_descriptions calls repeatedly at shrinking fontsizes
    (step 3) until the result fits."""
    lines_per_unit = [_wrap_unit(u, wrap_width) for u in units]
    line_h = line_height_in(fontsize)
    heights = [len(lines) * line_h for lines in lines_per_unit]
    min_gap = min_gap_ratio * line_h
    padding = padding_ratio * line_h

    block_tops, landings, text_bottoms = _push_down(units, heights, frame_top, min_gap, padding)

    # Push-up is a fallback, not a default: only attempted once the push-down
    # cascade has carried the deepest landing past the bottom of the frame.
    if landings and landings[-1] < frame_bottom:
        _pull_up_slack(units, heights, block_tops, landings, text_bottoms, frame_top, frame_bottom, min_gap, padding)

    return [
        PlacedDescription(
            landing_y=landings[i],
            block_top_y=block_tops[i],
            connector=_classify(landings[i], unit.slot_bot, unit.is_last),
            lines=lines_per_unit[i],
            fontsize=fontsize,
        )
        for i, unit in enumerate(units)
    ]


def place_descriptions(
    units: list[DescriptionUnit],
    frame_top: float,
    frame_bottom: float,
    wrap_width: int = 30,
    min_gap_ratio: float = 0.6329,
    padding_ratio: float = 0.3956,
    fontsize_default: float = 6.5,
) -> list[PlacedDescription]:
    """Place every unit's description block. If the push-down cascade (plus
    the push-up fallback) still leaves the deepest landing past frame_bottom,
    font size is shrunk (min_gap and padding shrink proportionally with it,
    via the ratios) and the whole layout is recomputed from scratch --
    smaller text can make units that needed pushing fit neatly again, so
    this is a full reset rather than a patch. Because every component of
    the stack's height scales with font size, there's no fixed floor: some
    small enough font always fits within any positive frame_bottom.

    `wrap_width` is the character-count wrap width at fontsize_default; at
    every smaller fontsize tried, it's rescaled via _scaled_wrap_width so a
    line keeps roughly the same page-inch width instead of shrinking along
    with the font -- see the module docstring's point 3."""
    if not units:
        return []
    fontsize = fontsize_default
    placed = _place_at_fontsize(units, wrap_width, frame_top, frame_bottom, min_gap_ratio, padding_ratio, fontsize)
    # This is step 3 of the algorithm: a "keep trying smaller until it
    # fits" loop. Each pass shrinks fontsize by SHRINK_FACTOR (10%
    # smaller each time) and re-runs the *entire* layout (steps 1 and 2)
    # from scratch at that new size -- not a tweak to the previous
    # attempt. `fontsize > FONTSIZE_FLOOR` is just a safety net so the
    # loop can't spin forever if something totally unexpected happened;
    # in normal use the fit is found long before fontsize gets anywhere
    # near that floor.
    while min(p.landing_y for p in placed) < frame_bottom and fontsize > FONTSIZE_FLOOR:
        fontsize *= SHRINK_FACTOR
        scaled_wrap_width = _scaled_wrap_width(wrap_width, fontsize_default, fontsize)
        placed = _place_at_fontsize(units, scaled_wrap_width, frame_top, frame_bottom, min_gap_ratio, padding_ratio, fontsize)
    return placed
