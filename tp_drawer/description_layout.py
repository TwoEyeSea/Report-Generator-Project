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
     keep rising to continue the chain past that clamp).

     This is a CASCADE, not a single rigid jump -- it walks backward
     junction by junction (last unit <-> its predecessor, then that
     predecessor <-> *its* predecessor, and so on), and at each junction it
     takes only the smaller of (a) the headroom actually available there
     (the untouched gap between that junction's two units, before this
     unit ever considered moving) and (b) whatever's still left of the
     deficit. The moment the deficit reaches zero, the cascade stops --
     it never reaches one junction further back than the deficit actually
     required, and it never takes more from a junction than that junction
     has to give. A unit that never gets reached by the cascade is left
     completely untouched: its landing, block, and connector classification
     are byte-for-byte whatever _push_down already computed for it.

     Concretely: unit N (last) first tries to close the whole deficit using
     only the headroom directly above it. If that's enough, ONLY unit N
     moves, by exactly that amount, and nothing else in the whole stack is
     touched -- the smallest possible fix. If it's not enough, N is now
     "pinned" against its own ceiling (predecessor N-1's text), and the
     *only* way to free more room for N is to also lift N-1 -- so the
     cascade steps back to the N-2 <-> N-1 junction and asks the same
     question there: how much of the still-remaining deficit can N-1's own
     headroom (against N-2's text) supply? If the chain still isn't
     satisfied, it keeps stepping back one junction at a time. At every
     step, only the *newly reached* predecessor gets its first increment;
     every unit already in the moving group receives that same fresh
     increment too (to keep riding the newly-raised ceiling above it),
     which is what carries earlier contributions all the way down to N.
     The net effect: units
     nearer the overflow accumulate the *sum* of every increment used
     below them and above them in the chain (they need all of it to reach
     the target), while a unit further back only accumulates the
     increments contributed by junctions at or below its own position --
     never inheriting a rise that occurred before it was needed. No
     unit's own internal top-anchor slack or gap to a neighbour it did
     NOT need to lean on is ever touched, which is what keeps this the
     minimum-disruption fix rather than one uniform block-wide shove.

     The first unit's *block* is exempt from shifting at all: its ceiling
     is the frame itself (frame_top) rather than a preceding unit's text,
     and frame_top sits deliberately above the grade line for other
     purposes, so letting it rise would run its text above ground level,
     which must never happen -- its block always stays at its own natural
     top-anchored position, and the cascade cannot reach past it (reaching
     the junction just below the first unit is the last step it can ever
     take). Its *landing* is a separate matter, exactly mirroring the last
     unit's block/landing split (just mirrored top-for-bottom): only if
     the group ends up climbing all the way back to sit directly below the
     first unit, AND the first unit genuinely has slack (its own text ends
     above its own landing -- see `slack` in the module docstring's
     opening paragraphs), does its landing get pulled up to close the gap
     -- and only up to its own real text-bottom, never further. If it has
     no slack, its landing is left exactly where _push_down put it. This
     same slack-gated rule applies to *whichever* unit ends up as the
     immediate predecessor of the final moved group, not just the first
     unit specifically -- a predecessor with no slack of its own must never
     have its landing forced to a new value just because something below
     it moved, since its landing already correctly reflects its own text's
     true extent. (This was a real, fixed bug: the landing-pull step used
     to run unconditionally, snapping a predecessor's already-correct
     "down" connector to an incorrect flat one whenever it happened to be
     adjacent to a moved group, even though nothing about its own text had
     changed.) Both the first and last unit can still be pushed down if
     genuinely crowded -- only the upward direction is restricted, and only
     for these two units' blocks specifically.
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
     of the page, instead scoot labels *up* -- but like a row of dominoes
     falling in reverse, one at a time: try nudging just the very last
     label up first, using only the free space already directly above it.
     If that alone closes the gap, stop there -- nothing else on the page
     moves. Only if it's not enough does the *next* label up also get
     nudged, contributing its own free space too, and so on, one label
     further back at a time, only ever as far as still needed. This way
     no label ever gets shoved further than the minimum required, and a
     label that was never needed to close the gap is never touched at all.
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


def _catch_up_landing(landings: list[float], i: int, floor: float, min_gap: float) -> None:
    """Raise landings[i] so it never sits stranded below floor + min_gap --
    but never lowers it (max, not assignment), since a predecessor may
    already legitimately sit higher than that for its own, unrelated
    reasons. `floor` is always the successor's own (possibly just-moved)
    block_top, so this is the one shared move both _push_down and
    _pull_up_slack make once they've decided a predecessor's landing needs
    to track a successor that just encroached into its slack: see each
    caller's own gating condition (why THIS is the moment to call it) in
    its own docstring -- that condition is what differs between the two
    cascades, not this update itself."""
    landings[i] = max(landings[i], floor + min_gap)


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
    overflow past slot_bot drags the landing down too.

    RETROACTIVE LANDING CATCH-UP -- keeping a slack predecessor's tick in
    step, but ONLY when its slack was actually the thing that let the
    successor rise:
    Letting a successor's block rise into a slack predecessor's *unused*
    space (between where that predecessor's text ends and its landing,
    down at slot_bot) is the whole point of measuring the ceiling against
    text, not landing -- see above. When that actually happens -- i.e.
    block_tops[i] is ceiling-constrained, `min()` above picked `ceiling`
    over the unit's own natural top-anchor -- the predecessor's landing
    tick can end up stranded below where the very next thing on the page
    now actually starts, and gets raised to close that gap: never lowered,
    and never past that predecessor's own real text_bottom (which the
    ceiling computation guarantees block_tops[i] + min_gap can never
    exceed, so this is always a valid landing position, not a new
    overflow).

    This must NOT run when block_tops[i] instead won on its own natural
    top-anchor (ceiling wasn't binding) -- that's the ordinary, unrelieved
    case where a unit simply sits at its own slot_top with a small
    (harmless, load-bearing-nowhere-else) padding-vs-min_gap sliver between
    it and whatever's above, regardless of whether the unit above happens
    to have slack. Catching that case up too would mean *every* slack
    ("neutral") unit followed by an ordinary one gets its landing nudged
    for no real reason -- true crowding never occurred, there is no
    stranded tick to rescue, and it would silently turn correct flat
    connectors into "up" ones throughout perfectly ordinary, uncrowded
    stacks. This mirrors _pull_up_slack's identical, equally-gated
    treatment of the junction where a push-up contribution actually lands
    -- same rule, same "only when genuine encroachment happened" gate,
    applied here to every consecutive pair as the forward cascade runs."""
    n = len(units)
    block_tops = [0.0] * n
    landings = [0.0] * n
    text_bottoms = [0.0] * n
    prev_text_bottom = frame_top
    for i, unit in enumerate(units):
        ceiling = prev_text_bottom - min_gap
        natural_top = unit.slot_top - padding
        block_tops[i] = min(natural_top, ceiling)
        if i > 0 and ceiling <= natural_top:  # genuinely ceiling-constrained, not just naturally close
            _catch_up_landing(landings, i - 1, block_tops[i], min_gap)
        natural_bottom = block_tops[i] - padding - heights[i]
        landings[i] = min(unit.slot_bot, natural_bottom)
        text_bottoms[i] = natural_bottom
        prev_text_bottom = natural_bottom
    return block_tops, landings, text_bottoms


def _pull_up_slack(
    units: list[DescriptionUnit],
    block_tops: list[float],
    landings: list[float],
    text_bottoms: list[float],
    frame_bottom: float,
    min_gap: float,
) -> None:
    """Step 2 of the algorithm: after step 1 (_push_down) has run and the
    last unit's landing still overflows past the bottom of the frame,
    CASCADE a minimal upward shift back through as few preceding units as
    possible -- see the module docstring's "Push up" section for the full
    reasoning; this docstring focuses on the mechanics. Modifies
    block_tops/landings in place (rather than returning new lists) to slot
    its results into the arrays _push_down already built.

    Only called when the push-down cascade has pushed the last unit's
    landing past the frame's bottom edge. (It's always the *last* unit
    that's deepest: push_down's cascade only ever pushes each unit's
    landing further down than the one above it -- both because each
    unit's own true depth (slot_bot) is deeper than its predecessor's, and
    because a crowded predecessor's overflow only ever pushes a successor
    down, never up -- so the last unit's landing is always the single
    deepest point in the whole stack. Checking only landings[-1] is
    therefore enough; no other unit needs a separate check.)

    THE TARGET -- how far the cascade needs to reach in total:
    The deficit is frame_bottom - landings[-1]. But the last unit's
    landing is never allowed to rise above its own neutral slot_bot (see
    the module docstring) regardless of how much the deficit demands, so
    `remaining` -- the running total still owed -- starts at whichever is
    smaller: the deficit itself, or the headroom already available between
    the last landing and its own slot_bot. If that's already zero or
    negative (the last unit is already sitting right at its own neutral
    ceiling), push-up has nothing left to give and the whole deficit is
    left for the font-shrink step to resolve.

    THE CASCADE -- walking junction by junction, back to front:
    `i` counts down from the last unit's index to 1, treating each `i` as
    "the junction between predecessor units[i - 1] and units[i]". At each
    junction:
      - headroom = the UNTOUCHED gap there: text_bottoms[i - 1] - min_gap
        - block_tops[i]. This is always safe to read directly (not
        accumulated/cached) because a unit's own block_tops/text_bottoms
        entry is only ever written by an EARLIER iteration of this same
        loop once that specific index has been added to the moving group
        -- and the loop only ever adds indices >= i on iteration i, so
        index i and index i - 1 are still guaranteed untouched the first
        time this junction is examined.
      - contribution = min(remaining, headroom) -- never more than the
        junction actually has, never more than what's still owed.
      - if contribution > 0: every unit from i to the end (range(i, n))
        receives += contribution on both block_top and landing. On the
        very first pass this is just the last unit; each subsequent pass
        extends the affected range one unit further back, so a unit
        nearer the overflow keeps receiving every later increment too --
        this is what accumulates the full total rise at the tail while
        each predecessor only carries the increments from its own
        junction onward (see the module docstring for why that's the
        physically-correct distribution, not an approximation of it).
      - remaining -= contribution. The loop exits the instant remaining
        <= 0 -- no further junction is ever touched once the deficit is
        satisfied, which is what keeps this a minimum-disruption fix
        rather than a uniform block-wide shove.
      - if units[i - 1].is_first: this was necessarily the last usable
        junction (that unit's block can never move -- see the module
        docstring), so the loop stops here regardless of whether
        `remaining` reached zero. Any leftover is left for font-shrink.

    RETROACTIVE LANDING CATCH-UP -- keeping a junction's predecessor tick in
    step, but ONLY at a junction that actually contributed:
    `headroom` here is measured against `text_bottoms` (the actual, unmoved
    bottom edge of the text above), the same choice _push_down makes and
    for the same reason -- see that function's docstring, including why
    this catch-up must be gated on genuine use of that headroom rather than
    applied everywhere. Exactly when `contribution > 0` -- this junction's
    predecessor really did just get leaned on to free up real room -- its
    landing is raised to close the gap with the successor's new block_top,
    never lowered, and never past its own real text_bottom (which headroom
    being non-negative already guarantees this can't exceed). A junction
    with zero contribution is left alone, for the same reason _push_down
    leaves an unconstrained junction alone: nothing was actually taken from
    that predecessor, so there's no stranded tick to rescue there -- either
    it was already fine, or _push_down's own matching catch-up already
    handled it during that earlier pass. A pair further along inside the
    same moved group, where BOTH sides shift by the same later increment,
    needs no separate catch-up either: equal increments preserve whatever
    gap already held between them."""
    n = len(units)
    last = units[-1]
    deficit = frame_bottom - landings[-1]
    remaining = min(deficit, last.slot_bot - landings[-1])
    if remaining <= 0:
        return  # the last unit is already at its own neutral ceiling -- push-up can't help

    # ADVANCED TECHNIQUE -- mutating the caller's lists in place:
    # Unlike most functions in this file, _pull_up_slack doesn't return
    # new lists -- it directly edits the block_tops/landings lists that
    # were passed in. That works because Python lists are passed by
    # reference: `block_tops` here is the *same* list object
    # _place_at_fontsize created, not a copy, so changes made to it here
    # are visible back in _place_at_fontsize once this function returns --
    # which is why this function's own return type is `None`; its whole
    # effect is these in-place edits.
    for i in range(n - 1, 0, -1):
        if remaining <= 0:
            break
        headroom = max(0.0, text_bottoms[i - 1] - min_gap - block_tops[i])
        contribution = min(remaining, headroom)
        if contribution > 0:
            for j in range(i, n):
                block_tops[j] += contribution
                landings[j] += contribution
            remaining -= contribution
            _catch_up_landing(landings, i - 1, block_tops[i], min_gap)
        if units[i - 1].is_first:
            break  # its block can never move -- this is the last usable junction


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
        _pull_up_slack(units, block_tops, landings, text_bottoms, frame_bottom, min_gap)

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
