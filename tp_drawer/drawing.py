"""Renders a Project to a multi-page PDF, one page per trial pit.

This is the "pen" of the program -- everything upstream (excel_io.py,
catalog.py, models.py) is about gathering and organizing data; this file
is the only place that actually draws anything, using the matplotlib
library. The mental model to hold onto throughout this file: a
matplotlib "figure" is one whole page/canvas, and an "axes" is the
coordinate system drawn on top of it that you place shapes into by
giving x/y coordinates -- see _new_axes below, where the axes are set up
to span exactly the page's width and height in inches, so every x/y
coordinate used elsewhere in this file (e.g. "draw a line from (2.3, 5)
to (4.3, 5)") means a literal position in inches on the printed page.

render_project (at the bottom of this file) is the single entry point
everything else leads up to: it loops over every pit in the project, and
for each one calls render_pit_page, which in turn calls the _draw_xxx
helpers above it to build up one whole page -- the stratigraphy column,
the general notes box, and the title block. Read the file bottom-to-top
if you want the "big picture first, details later" order; it's laid out
top-to-bottom instead because Python requires a function to be defined
before something above it can call it... except each _draw_xxx here is
only *called* by something further down, so there's no strict need to
read it in file order.
"""

import math
import textwrap
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import matplotlib

# ADVANCED TECHNIQUE -- choosing a matplotlib "backend":
# matplotlib can draw either to an interactive on-screen window or
# straight to a file, and which one it does is controlled by its
# "backend". "Agg" (Anti-Grain Geometry) is a backend that only ever
# renders to an image/file buffer -- it has no concept of a window at
# all. This program runs as a command-line tool / web server with no
# screen to show a plot on, so forcing Agg here (before matplotlib gets a
# chance to guess and maybe pick a GUI backend that isn't even installed)
# avoids a whole class of "no display found" crashes on a server.
matplotlib.use("Agg")  # headless PDF generation only, never needs a GUI backend

import io

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Circle, Polygon, Rectangle
from matplotlib.path import Path as ClipPath
from matplotlib.transforms import Affine2D
from PIL import Image, ImageCms

from tp_drawer.catalog import UnitTemplate, find_template, load_catalog
from tp_drawer.config import Config
from tp_drawer.description_layout import DescriptionUnit, line_height_in, place_descriptions
from tp_drawer.hatch_patterns import PATTERN_REGISTRY, Blob, Dot, LineSegment
from tp_drawer.layout import band_y_range, compute_scale_preferring_fixed, y_at_depth
from tp_drawer.models import DEFAULT_TERMINATION_REASON, Project, ProjectInfo, TrialPit
from tp_drawer.units import format_feet_inches

# Frame geometry, in page inches. All pits in a build share one true scale,
# normally the fixed FIXED_COLUMN_SCALE (a real, nameable scale) unless the
# deepest pit is too deep to fit the page at it, in which case the scale
# zooms out just enough to make the deepest pit's column exactly fill
# COLUMN_HEIGHT_BUDGET instead -- see compute_project_scale and
# compute_scale_preferring_fixed. Shallower pits always draw proportionally
# shorter columns than the deepest one, whichever way the scale was decided.
# The frame's
# bottom edge rests directly on top of the general notes box below it (no
# gap), so the unit-description stack gets full use of the space right down
# to the notes -- its push-up/shrink logic guarantees nothing ever crosses
# this line. FRAME_TOP_Y sits just below the page's outer margin -- raised
# up from its old position now that the "TRIAL PIT No." title above it is
# gone, reclaiming that space for the frame itself.
MARGIN = 0.4

# The page's own outermost border (drawn at the very start of
# render_pit_page, around the full MARGIN..page_size-MARGIN rectangle) --
# the boldest stroke on the whole page, same idea as
# TITLE_BLOCK_BORDER_LINEWIDTH below for the title block's own outer
# frame, just one level up: this border encloses everything else (title
# block included), so it's sized to read as the outermost frame, not just
# another box.
PAGE_BORDER_LINEWIDTH = 2.5

FRAME_TOP_Y = 7.8
GENERAL_NOTES_HEIGHT = 1.3
FRAME_BOTTOM_Y = MARGIN + GENERAL_NOTES_HEIGHT
FRAME_HEIGHT = FRAME_TOP_Y - FRAME_BOTTOM_Y

# The true-scale column is calibrated against a slightly shorter budget than
# the full frame height, leaving a small breathing-room margin between the
# deepest pit's column bottom edge and FRAME_BOTTOM_Y (the general notes
# box below it), so the column's own border never touches the notes box.
# Reducing the budget makes compute_scale zoom every pit's column out
# slightly to make room for this margin.
COLUMN_BOTTOM_PADDING = 0.3
COLUMN_HEIGHT_BUDGET = FRAME_HEIGHT - COLUMN_BOTTOM_PADDING

# Page-inches per real inch of depth: "1 inch = 2 feet" (1/24), the scale
# compute_project_scale below prefers whenever a project's deepest pit
# fits within COLUMN_HEIGHT_BUDGET at it (up to ~11'-7" deep) -- only a
# pit deeper than that falls back to compute_scale's own "zoom to exactly
# fill the frame" ratio. Without this, a shallow pit gets stretched to
# fill the whole page just for being the deepest thing in its project;
# see compute_scale_preferring_fixed's own docstring for the full reasoning.
FIXED_COLUMN_SCALE = 1 / 24

# figure_display_box: the ceiling the unit-description stack pushes up
# against (see description_layout.py). Its bottom is FRAME_BOTTOM_Y, same as
# the true-scale column's. Its top sits a little above FRAME_TOP_Y -- the
# grade line itself, not just some headroom above it -- so FRAME_TOP_Y is
# fully inside the box rather than sitting exactly on its edge.
FIGURE_TOP_MARGIN = 0.2
FIGURE_TOP_Y = FRAME_TOP_Y + FIGURE_TOP_MARGIN
COLUMN_X = 2.3
COLUMN_W = 2.0  # pit column width, drawn at 2'-0" -> 2.0in on the page (sheet is N.T.S.)
DIM_X = COLUMN_X + COLUMN_W + 0.45  # shared vertical "spine" for per-layer dimensions and depth landings -- wide enough that the accumulated-depth label clears the dimension line
LABEL_X = DIM_X + 0.55

# Per-layer thickness dimension line (vertical, at DIM_X). Arrowheads are only
# drawn when the layer is thicker than this -- thin layers keep a plain line.
# Tips are inset slightly off the true y_top/y_bot: two adjacent layers'
# dimension lines meet at the exact same shared boundary point, and drawing
# both arrowheads' tips exactly there makes them clip into each other (same
# issue at the very top, where the first layer's tip would otherwise land
# exactly on the FRAME_TOP_Y grade line).
DIM_ARROW_THRESHOLD_IN = Decimal(8)
DIM_ARROW_LEN = 0.045
DIM_ARROW_HALF_W = 0.01
DIM_ARROW_INSET = 0.03

# Depth landing: at the base of every unit, a horizontal tick from the column
# to the spine (DIM_X). The accumulated-depth label sits directly above this
# tick (not out on the dimension line or any diagonal) -- no diagonal here,
# that's a distinct thing from the unit-description landings' diagonals below.
LANDING_TEXT_GAP = 0.02  # from the column, not DIM_X -- keeps the label over the tick itself
LANDING_TEXT_Y_PAD = 0.06  # just clears the tick line

# Unit description landings: each layer's name+description is its own text
# block, stacked independently of the true-scale column by
# description_layout.place_descriptions(). A tick runs from the column to
# DESC_SPINE_X at the unit's true depth, then a line continues out to the
# text at LABEL_X -- flat when the block's landing matches true depth
# (including the last unit's default, uncrowded state), sloping down/up
# when the reflow moved the block off its true position. No arrowhead,
# matching the accumulated-depth landings above. Shares DIM_X with the
# depth-landing/dimension spine -- one shared vertical line, so the
# description connector starts exactly where the depth-landing tick ends.
DESC_SPINE_X = DIM_X
DESC_TEXT_GAP = 0.05  # gap between the connector's landing end and where text starts
DESC_LANDING_LINE_WIDTH = 1.8  # length of the landing line drawn under each unit description, at DESC_FONTSIZE_DEFAULT -- scales with fontsize like the text itself
DESC_WRAP_WIDTH = 45
DESC_FONTSIZE_DEFAULT = 6.5
# min_gap and padding as ratios of line height, not fixed inches, so they
# shrink proportionally with the font -- see description_layout.py. Ratios
# chosen to reproduce the originally-tuned 0.1in / 0.05in gaps at the
# default font size.
DESC_MIN_GAP_RATIO = 0.1 / line_height_in(DESC_FONTSIZE_DEFAULT)
DESC_PADDING_RATIO = 0.05 / line_height_in(DESC_FONTSIZE_DEFAULT)

# Termination caption: one or two lines of text (a bare formation name
# wraps to "<FORMATION> \nENCOUNTERED AT DEPTH" -- two lines -- while the
# DEFAULT_TERMINATION_REASON sentinel is shown as-is, one line; see
# _termination_caption) drawn directly under the *last* unit description's
# own landing line, left-aligned with the description text at LABEL_X, at
# whatever fontsize the last description ended up placed at (see
# _termination_caption and its call site in _draw_stratigraphy_column).
# Because it isn't one of the DescriptionUnit objects description_layout.py
# knows about, its own vertical space has to be reserved by hand:
# TERMINATION_RESERVED_HEIGHT is added on top of FRAME_BOTTOM_Y before
# place_descriptions ever sees it, so its push-down/push-up/shrink logic
# always treats the true bottom of the page as being this much higher than
# it actually is -- guaranteeing a landing never ends up so low that this
# caption would have nowhere left to go. Reserved for TWO lines
# unconditionally (not just whichever this particular pit's caption
# happens to need) -- deliberately over-reserving for the worst case
# rather than branching on pit.termination_reason here, matching sizing
# from DESC_FONTSIZE_DEFAULT below: both exist so the reserved space is
# always at least as big as the caption could ever actually need,
# regardless of which pit or how much the rest of the descriptions end up
# shrinking, rather than being cut exactly to fit one specific case.
TERMINATION_TEXT_GAP = 0.04  # gap between the last unit's landing line and the caption below it
TERMINATION_RESERVED_HEIGHT = 2 * line_height_in(DESC_FONTSIZE_DEFAULT) + TERMINATION_TEXT_GAP

# Groundwater symbol: a "landing" (a horizontal line that stops short of the
# column) carries the label text and the triangle+lines symbol; a diagonal
# line then drops from the landing's column-side end to the column at the
# exact groundwater depth. Landing geometry is fixed relative to the column,
# so it never collides with it regardless of COLUMN_W.
GW_LANDING_RIGHT_X = COLUMN_X - 0.3
GW_LANDING_LEFT_X = MARGIN + 0.2
GW_LANDING_RISE_IN = Decimal(3)  # landing sits 3" of REAL depth above the actual water table, scaled like everything else
GW_SYMBOL_X = GW_LANDING_LEFT_X  # symbol's axis of symmetry == landing's left edge
GW_GAP = 0.025  # equal padding: triangle-to-line1, line1-to-line2, line2-to-line3, line3-to-landing
GW_TRIANGLE_HALF_W = 0.085
GW_TRIANGLE_H = 0.11
GW_LINE1_HALF_W = 0.085
GW_LINE2_HALF_W = 0.06
GW_LINE3_HALF_W = 0.035
GW_TEXT_X_PAD = 0.16  # horizontal gap between the symbol and the label text
GW_TEXT_Y_PAD = 0.03  # vertical gap between the landing and the label text
GW_TEXT_FONTSIZE = 5

MAIN_ZONE_RIGHT = 7.5
TITLE_BLOCK_X = MAIN_ZONE_RIGHT + 0.1
TITLE_BLOCK_W = 3.0

# The title block's own OUTER border (drawn once, wrapping the whole stack
# of NOTES/PROJECT/TITLE/DRAWN BY/SCALE/FILE/logo boxes -- see the last
# line of _draw_title_block) is deliberately bolder than the sharp-
# cornered, thinner border each individual box inside it gets from
# draw_box() -- that contrast is what makes it read as the title block's
# own enclosing frame rather than just another one of the boxes stacked
# within it.
TITLE_BLOCK_BORDER_LINEWIDTH = 2.0  # vs. draw_box()'s fixed 0.8 for every box inside it

# Per-box text styling: every labelled box drawn by draw_box() -- the
# general notes box at the bottom left, plus every box in the title block
# column (NOTES, PROJECT, TITLE, DRAWN BY, SCALE, FILE) -- gets its own
# named fontsize and linespacing here, rather than sharing one setting.
# linespacing is matplotlib's own Text.linespacing: a multiplier of
# fontsize applied between line baselines within a box's body text (only
# visibly matters for boxes whose body text wraps to more than one line,
# e.g. NOTES/PROJECT, but every box gets one for consistency and so a
# short field can still be grown into a wrapped one later without having
# to remember to add a linespacing setting for it then).
GENERAL_NOTES_FONTSIZE = 6.8
GENERAL_NOTES_LINESPACING = 1.8
TITLE_BLOCK_NOTES_FONTSIZE = 6.8
TITLE_BLOCK_NOTES_LINESPACING = 1.8
TITLE_BLOCK_PROJECT_FONTSIZE = 6.8
TITLE_BLOCK_PROJECT_LINESPACING = 1.2
TITLE_BLOCK_TITLE_FONTSIZE = 6.8
TITLE_BLOCK_TITLE_LINESPACING = 0.8
TITLE_BLOCK_DRAWN_BY_FONTSIZE = 6.8
TITLE_BLOCK_DRAWN_BY_LINESPACING = 0.8
TITLE_BLOCK_SCALE_FONTSIZE = 6.8
TITLE_BLOCK_SCALE_LINESPACING = 0.8
TITLE_BLOCK_FILE_FONTSIZE = 6.8
TITLE_BLOCK_FILE_LINESPACING = 0.8

GENERAL_NOTES_BOILERPLATE = (
    "1) {equipment_note}\n"
    "2) GROUND LEVELS ARE APPROXIMATE AND BASED UPON LOCAL KNOWLEDGE ONLY.\n"
    "3) TRIAL PIT EXCAVATION CARRIED OUT ON {date}.\n"
    "4) THIS TRIAL PIT LOG TO BE READ IN CONJUNCTION WITH SITE INSPECTION REPORT NO. 1, {file_ref}\n"
    "5) {groundwater_note}\n"
    "6) {bedrock_note}"
)

TITLE_BLOCK_NOTES_BOILERPLATE = (
    "1) {equipment_note}\n"
    "2) SUBSOILS INVESTIGATION CARRIED OUT ON {date}.\n"
    "3) THIS TRIAL PIT LOG TO BE READ IN CONJUNCTION WITH REPORT NO. {file_ref}\n"
    "4) {groundwater_note}\n"
    "5) {wall_stability_note}"
)


def _new_axes(cfg: Config):
    """Set up one blank page: a matplotlib "figure" (the whole canvas,
    sized to the page's physical dimensions in inches) and an "axes" (the
    coordinate system drawn onto it, deliberately stretched via
    set_xlim/set_ylim to match those same inches 1-for-1, so a point at
    x=2.3 really is 2.3 inches from the page's left edge). ax.axis("off")
    hides the usual chart decorations (tick marks, axis lines) that
    matplotlib draws by default -- this is a technical drawing, not a
    chart, so none of that is wanted. Every _draw_xxx function in this
    file receives this same `ax` and adds its shapes onto it."""
    # dpi controls the render resolution the PDF backend rasterizes embedded raster
    # images (the logo) to before writing them as PDF XObjects -- vector content (lines,
    # text, patches) is unaffected. The default rcParams dpi (100) downsamples the
    # 1319x378 logo source to ~260x75px in the output, visibly pixelating it.
    fig = plt.figure(figsize=cfg.page_size_in, dpi=300)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, cfg.page_size_in[0])
    ax.set_ylim(0, cfg.page_size_in[1])
    # "equal" aspect means one inch on the x-axis is drawn the same
    # length on the page as one inch on the y-axis -- without this, a
    # square could stretch into a rectangle if the axes box itself wasn't
    # perfectly square, which would distort every dimension on the page.
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def draw_box(
    ax, x: float, y: float, w: float, h: float, label: str, body_text: str = "",
    fontsize: float = 6.5, linespacing: float = 1.2,
) -> None:
    """A reusable "labelled box" building block: draws a rectangle outline
    with a bold label in its top-left corner and, optionally, a line of
    body text just below the label. Used throughout the title block and
    general notes box below -- every bordered field on the drawing (NOTES:,
    PROJECT:, DRAWN BY:, ...) is one call to this same function with
    different position/size/text.

    fontsize and linespacing are NOT meant to be shared across boxes --
    every call site below passes its own explicit values (see the
    GENERAL_NOTES_*/TITLE_BLOCK_*_FONTSIZE/LINESPACING constants near the
    top of this file), so each box's text density can be tuned in
    isolation. The defaults here only apply if a caller genuinely doesn't
    care."""
    label_pad = 0.11
    line_gap = 0.15
    ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor="black", linewidth=0.8))
    ax.text(x + 0.05, y + h - label_pad, label, fontsize=fontsize, fontweight="bold", va="top", ha="left")
    if body_text:
        ax.text(x + 0.05, y + h - label_pad - line_gap, body_text, fontsize=fontsize, linespacing=linespacing, va="top", ha="left")


def _equipment_note(info: ProjectInfo, *, template: str) -> str:
    """Full text for a general/title-block notes box's equipment line --
    returns the *whole* sentence rather than filling blanks into a fixed
    template, so a project with no recorded equipment reads as a
    complete sentence ("GROUND CONDITIONS VISUALLY CONFIRMED BY THE
    GEOTECHNICAL ENGINEER.") instead of "...WITH A - SUPPLIED BY -."
    Equipment and equipment provider are always filled in together on
    the input form -- one blank always means both are -- so either one
    missing is enough to trigger the fallback, without needing to treat
    "equipment known, provider unknown" as its own separate case.
    `template` lets the general notes box (mentions the provider) and
    title block notes box (doesn't) keep their own existing wording for
    the case where equipment info is present, with one {equipment}/
    {equipment_provider}-style placeholder each."""
    if not info.equipment.strip() or not info.equipment_provider.strip():
        return "GROUND CONDITIONS VISUALLY CONFIRMED BY THE GEOTECHNICAL ENGINEER."
    # .rstrip(".") on the provider: it's re-appended once by the template
    # itself (every template here ends "...{equipment_provider}."), and a
    # provider name that already ends in a period (e.g. "...Ltd.") would
    # otherwise print a double one.
    return template.format(equipment=info.equipment.upper(), equipment_provider=info.equipment_provider.rstrip(".").upper())


def _groundwater_short(pit: TrialPit) -> str:
    """One-line groundwater summary, e.g. "7'-2" BELOW GRADE" or "NOT
    ENCOUNTERED" -- reused in both the title block notes and the general
    notes box, so the wording only needs to be decided in one place."""
    if pit.groundwater_depth_in is None:
        return "NOT ENCOUNTERED"
    return f"{format_feet_inches(pit.groundwater_depth_in)} BELOW GRADE"


def _groundwater_note(pit: TrialPit, *, verb: str) -> str:
    """Full text for a general/title-block notes box's groundwater line --
    returns the *whole* sentence rather than a depth to slot into a fixed
    "...WAS ENCOUNTERED ... AT {groundwater}." template, so a pit with no
    recorded groundwater reads as a complete, grammatical sentence
    ("GROUNDWATER WAS NOT ENCOUNTERED THROUGHOUT THIS EXCAVATION.")
    instead of the old template producing the nonsensical
    "...AT NOT ENCOUNTERED." `verb` ("DURING"/"THROUGHOUT") lets the
    general notes box and title block notes box keep their own existing
    wording for the encountered case, while both share the same clean
    sentence for the not-encountered case."""
    if pit.groundwater_depth_in is None:
        return "GROUNDWATER WAS NOT ENCOUNTERED THROUGHOUT THIS EXCAVATION."
    return f"GROUNDWATER WAS ENCOUNTERED {verb} THE EXCAVATION AT {_groundwater_short(pit).upper()}."


def _wall_stability_note(pit: TrialPit) -> str:
    """Item 5 of the title block notes box: whether this pit's own walls
    stayed structurally sound during excavation. pit.walls_stable
    defaults to True (see TrialPit's own docstring) for a pit with no
    "Pit walls stable?" entry at all, so an older input sheet keeps
    reading exactly as it always has."""
    if pit.walls_stable:
        return "STRUCTURAL INTEGRITY REMAINED SOUND WITHIN PIT WALLS."
    return "TRIAL PIT WALLS WERE UNSTABLE DURING THE EXCAVATION."


# Formation names that represent striking genuine, unweathered bedrock --
# as opposed to a weathered marl/soil horizon that's merely associated
# with a formation (Ironshore Formation Limestone is deliberately NOT
# included here: tp_drawer.report_io's formation catalog treats it the
# same way, wording its geological commentary as "Native Bedrock was not
# encountered... consolidated native marl was encountered..." even when
# Ironshore is the named final stratum). Matched case-insensitively
# against pit.termination_reason, which excel_io.py already stores
# upper-cased -- .lower() here just avoids relying on that detail.
_TRUE_BEDROCK_FORMATIONS = {"cayman formation dolostone", "pedro castle formation dolostone"}


def _bedrock_note(pit: TrialPit) -> str:
    """Item 6 of the general notes box: whether this pit's own final
    stratum represents true bedrock, purely from its termination_reason --
    a pit that bottomed out in fill/soil, in Ironshore Formation Limestone
    (see above), or wasn't assigned a final stratum at all (the
    DEFAULT_TERMINATION_REASON sentinel) all read as "not encountered"."""
    if pit.termination_reason.strip().lower() in _TRUE_BEDROCK_FORMATIONS:
        return "BEDROCK WAS ENCOUNTERED."
    return "BEDROCK WAS NOT ENCOUNTERED."


def _groundwater_label(pit: TrialPit) -> str:
    """Two-line label drawn next to the groundwater symbol itself (see
    _draw_groundwater_symbol below) -- a slightly more verbose version of
    _groundwater_short, since this one stands alone on the drawing rather
    than being folded into a sentence."""
    if pit.groundwater_depth_in is None:
        return "GROUNDWATER NOT ENCOUNTERED"
    return f"GROUNDWATER TABLE ENCOUNTERED\n{_groundwater_short(pit)}"


def _termination_caption(pit: TrialPit) -> str:
    """The short caption drawn under the last unit description's landing,
    describing what was found at the base of the pit.

    pit.termination_reason holds either the DEFAULT_TERMINATION_REASON
    sentinel (excel_io.py's fallback when no "Final Strata" was supplied
    for this pit) or a bare formation name (e.g. "IRONSHORE FORMATION
    MARL") read straight off the input sheet. Comparing against the
    sentinel is what decides which of the two captions to build: the
    sentinel is shown exactly as-is (there's no formation name to build a
    sentence around), while a real formation name gets wrapped into a
    full sentence here -- this is the one and only place that sentence
    gets assembled, so excel_io.py only ever has to store the bare name,
    never a rendering-ready string."""
    if pit.termination_reason == DEFAULT_TERMINATION_REASON:
        return DEFAULT_TERMINATION_REASON
    return f"{pit.termination_reason} \nENCOUNTERED AT DEPTH"


def _draw_groundwater_symbol(ax, gw_y: float, pit: TrialPit, scale: float) -> None:
    """Standard geotechnical water-table symbol on its "landing": a solid
    inverted triangle over three horizontal lines of decreasing width, all
    stacked with equal padding, sitting above a landing line. The landing
    stops short of the column; a diagonal line drops from its right end to
    the column at gw_y, the actual groundwater depth. The label text sits
    above the landing, to the right of the symbol."""
    landing_y = gw_y + float(GW_LANDING_RISE_IN) * scale

    ax.plot([GW_LANDING_LEFT_X, GW_LANDING_RIGHT_X], [landing_y, landing_y], color="black", linewidth=0.6)
    ax.plot([GW_LANDING_RIGHT_X, COLUMN_X], [landing_y, gw_y], color="black", linewidth=0.6)

    line3_y = landing_y + GW_GAP
    line2_y = line3_y + GW_GAP
    line1_y = line2_y + GW_GAP
    triangle_apex_y = line1_y + GW_GAP  # apex is the triangle's bottom (pointy) tip
    triangle_base_y = triangle_apex_y + GW_TRIANGLE_H

    ax.add_patch(
        Polygon(
            [
                (GW_SYMBOL_X - GW_TRIANGLE_HALF_W, triangle_base_y),
                (GW_SYMBOL_X + GW_TRIANGLE_HALF_W, triangle_base_y),
                (GW_SYMBOL_X, triangle_apex_y),
            ],
            closed=True,
            facecolor="black",
            edgecolor="black",
        )
    )
    for half_w, y in ((GW_LINE1_HALF_W, line1_y), (GW_LINE2_HALF_W, line2_y), (GW_LINE3_HALF_W, line3_y)):
        ax.plot([GW_SYMBOL_X - half_w, GW_SYMBOL_X + half_w], [y, y], color="black", linewidth=0.6)

    text_x = GW_SYMBOL_X + GW_TRIANGLE_HALF_W + GW_TEXT_X_PAD
    ax.text(
        text_x,
        landing_y + GW_TEXT_Y_PAD,
        _groundwater_label(pit),
        fontsize=GW_TEXT_FONTSIZE,
        va="bottom",
        ha="left",
    )


def _draw_arrow_toward(ax, from_xy: tuple[float, float], to_xy: tuple[float, float], length: float, half_width: float) -> None:
    """Filled triangular arrowhead at to_xy, pointing in the from_xy -> to_xy direction.

    This builds the arrowhead as a triangle: one corner is the arrow's
    tip (to_xy itself), and the other two corners sit a little way back
    along the line, offset sideways to left and right. The maths:
      1. (dx, dy) is the direction of travel; dividing by its own length
         (`dist`, via math.hypot -- a shortcut for sqrt(dx**2 + dy**2))
         turns it into a *unit vector* (ux, uy): same direction, but
         exactly 1 unit long, so it's now a pure "which way" with no
         "how far" mixed in.
      2. (px, py) = (-uy, ux) rotates that direction 90 degrees to get
         the *perpendicular* (sideways) direction -- the same "rotate a
         vector 90 degrees by swapping and negating one coordinate" trick
         used in hatch_patterns.py's _axes function.
      3. base_x/base_y is the point `length` back from the tip, along the
         original direction; the two non-tip corners are that point
         nudged sideways by half_width in each perpendicular direction.
    if dist == 0 guards against from_xy and to_xy being the exact same
    point, which would make "which direction is this arrow facing" a
    meaningless question (division by zero) -- in that edge case, this
    just draws nothing rather than crashing.
    """
    (x0, y0), (x1, y1) = from_xy, to_xy
    dx, dy = x1 - x0, y1 - y0
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    ux, uy = dx / dist, dy / dist
    px, py = -uy, ux
    base_x, base_y = x1 - ux * length, y1 - uy * length
    ax.add_patch(
        Polygon(
            [(base_x + px * half_width, base_y + py * half_width), (base_x - px * half_width, base_y - py * half_width), (x1, y1)],
            closed=True,
            facecolor="black",
            edgecolor="black",
        )
    )


def _draw_layer_dimension(ax, y_top: float, y_bot: float, thickness_in: Decimal) -> None:
    """Vertical dimension line for one layer's thickness, at the DIM_X spine.
    Arrowheads at each end only appear once the layer is thick enough to hold them."""
    ax.plot([DIM_X, DIM_X], [y_top, y_bot], color="black", linewidth=0.6)
    if thickness_in > DIM_ARROW_THRESHOLD_IN:
        _draw_arrow_toward(ax, (DIM_X, y_bot), (DIM_X, y_top - DIM_ARROW_INSET), DIM_ARROW_LEN, DIM_ARROW_HALF_W)
        _draw_arrow_toward(ax, (DIM_X, y_top), (DIM_X, y_bot + DIM_ARROW_INSET), DIM_ARROW_LEN, DIM_ARROW_HALF_W)
    ax.text(
        DIM_X + 0.08,
        (y_top + y_bot) / 2,
        format_feet_inches(thickness_in),
        fontsize=6.5,
        va="center",
        ha="left",
    )


def _draw_depth_landing(ax, boundary_y: float, accumulated_depth: Decimal) -> None:
    """Accumulated-depth label at the base of a unit: a flat tick from the
    column to the DIM_X spine, with the label sitting directly above that
    tick -- no diagonal, the last unit's landing shows the trial pit's final
    (termination) depth."""
    ax.plot([COLUMN_X + COLUMN_W, DIM_X], [boundary_y, boundary_y], color="black", linewidth=0.6)
    ax.text(
        COLUMN_X + COLUMN_W + LANDING_TEXT_GAP,
        boundary_y + LANDING_TEXT_Y_PAD,
        format_feet_inches(accumulated_depth),
        fontsize=6.5,
        va="bottom",
        ha="left",
    )


def _draw_description_connector(ax, column_edge_x: float, true_y: float, landing_y: float, fontsize: float) -> None:
    """Tick from the column to the description spine at the unit's true
    depth, then a line out to the text -- flat when landing_y matches
    true_y (including the last unit's default, uncrowded state), sloping
    down/up when the reflow moved the block off its true position. Ends in
    a landing line at landing_y, under the description text -- the same
    y that description_layout.py already re-solves on every push-down/
    push-up/shrink pass, so this always lands wherever the text actually
    ended up, scaled with the text's own fontsize."""
    ax.plot([column_edge_x, DESC_SPINE_X], [true_y, true_y], color="black", linewidth=0.6)
    landing_start_x = LABEL_X - DESC_TEXT_GAP
    ax.plot([DESC_SPINE_X, landing_start_x], [true_y, landing_y], color="black", linewidth=0.6)
    landing_width = DESC_LANDING_LINE_WIDTH * fontsize / DESC_FONTSIZE_DEFAULT
    ax.plot([landing_start_x, landing_start_x + landing_width], [landing_y, landing_y], color="black", linewidth=0.6)


def _draw_description_block(ax, placed) -> None:
    y = placed.block_top_y
    ax.text(LABEL_X, y, placed.lines[0], fontsize=placed.fontsize, fontweight="bold", va="top", ha="left")
    for line in placed.lines[1:]:
        y -= line_height_in(placed.fontsize)
        ax.text(LABEL_X, y, line, fontsize=placed.fontsize, va="top", ha="left")


def _draw_hatch(ax, x0: float, y0: float, width: float, height: float, pattern_id: str, angle: float, size: float, line_color: str) -> None:
    """Tiles PATTERN_REGISTRY[pattern_id]'s primitives across (x0, y0, width, height), clipped to that rectangle.

    This is the bridge between hatch_patterns.py's pure geometry and
    matplotlib's actual drawing objects. hatch_patterns.py doesn't know
    anything about matplotlib -- it just returns plain LineSegment/Dot/
    Blob data describing shapes -- so this function's job is to turn each
    one into a real matplotlib shape (a line segment, a Circle for a dot,
    a Polygon for a blob) positioned at the right spot on the page, and
    add it to the axes.

    ADVANCED TECHNIQUE -- batching into Collections, not individual
    artists: a densely-hatched layer can need hundreds of primitives, and
    matplotlib pays real per-artist overhead (bookkeeping, transforms, a
    separate draw() call) for each one added individually via
    ax.add_line()/ax.add_patch() -- confirmed directly on this project's
    own rendering (profiling a 4-pit generation showed roughly 85% of the
    total time was spent here). LineCollection and PatchCollection draw
    *all* their member shapes in one single batched call instead, which
    measured 3-5x faster in isolation with no visual difference at all --
    so every line segment this function produces goes into one shared
    LineCollection, and every dot/blob (Circle/Polygon patches) into one
    shared PatchCollection, rather than being added to the axes one at a
    time. match_original=True on the PatchCollection is what lets a mix
    of filled and unfilled dots (see Dot.filled) keep each one's own
    facecolor instead of forcing every patch in the collection to share
    a single, uniform style.

    ADVANCED TECHNIQUE -- isinstance branching (a simple form of "type
    dispatch"): `pattern.generate(...)` can hand back a mix of different
    primitive types in one list (see hatch_patterns.py's gravel pattern,
    which mixes Dot and Blob). `isinstance(primitive, LineSegment)` asks
    "is this specific object actually a LineSegment?", letting the loop
    sort each shape into the right bucket (line segments vs. patches)
    rather than needing three separate lists or a wrapper object with a
    "shape kind" field to check instead.

    ADVANCED TECHNIQUE -- clip paths (think: a stencil):
    Every pattern in hatch_patterns.py deliberately draws *past* the
    edges of its rectangle (see that file's module docstring) rather than
    trying to stop exactly at the boundary itself. `clip_path` here is
    what turns that overflow into a clean edge: it's built from
    ClipPath.unit_rectangle() (a generic 1x1 square Path shape) and an
    Affine2D transform that scales it up to (width, height) and slides it
    into position at (x0, y0) -- Affine2D is matplotlib's tool for
    combining scaling/rotating/moving operations. Calling
    `collection.set_clip_path(clip_path, ...)` once per collection (not
    once per primitive) tells matplotlib "only actually draw the parts of
    these shapes that fall inside this rectangle" -- exactly like laying
    a rectangular stencil over a page and spray-painting through it: the
    paint (the hatch primitives) can go anywhere, but only what's under
    the stencil's cutout (the clip path) ends up visible.
    """
    pattern = PATTERN_REGISTRY.get(pattern_id)
    if pattern is None or pattern_id == "none":
        return
    clip_path = ClipPath.unit_rectangle().transformed(Affine2D().scale(width, height).translate(x0, y0))
    line_segments = []
    patches = []
    for primitive in pattern.generate(width, height, angle, size):
        if isinstance(primitive, LineSegment):
            line_segments.append(((x0 + primitive.x1, y0 + primitive.y1), (x0 + primitive.x2, y0 + primitive.y2)))
        elif isinstance(primitive, Dot):
            patches.append(
                Circle(
                    (x0 + primitive.cx, y0 + primitive.cy),
                    primitive.r,
                    facecolor=line_color if primitive.filled else "none",
                    edgecolor=line_color,
                    linewidth=0.5,
                )
            )
        elif isinstance(primitive, Blob):
            patches.append(
                Polygon(
                    [(x0 + px, y0 + py) for px, py in primitive.points],
                    closed=True,
                    facecolor="none",
                    edgecolor=line_color,
                    linewidth=0.5,
                )
            )

    if line_segments:
        lines = LineCollection(line_segments, colors=line_color, linewidths=0.5)
        lines.set_clip_path(clip_path, ax.transData)
        ax.add_collection(lines)
    if patches:
        shapes = PatchCollection(patches, match_original=True)
        shapes.set_clip_path(clip_path, ax.transData)
        ax.add_collection(shapes)


def render_hatch_swatch(
    pattern_id: str,
    angle: float,
    size: float,
    background_color: str,
    line_color: str,
    width_in: float = 1.2,
    height_in: float = 0.8,
) -> bytes:
    """Renders a small standalone PNG preview of a hatch pattern -- used by the catalog page's live thumbnail.

    Unlike every other _draw_xxx function in this file, this one builds
    its *own* brand new tiny figure (plt.subplots(...)) rather than
    drawing onto a page that already exists -- it's used on-demand by the
    webapp's catalog editor to render a live "here's what this pattern
    looks like" preview image, completely independent of any actual
    trial pit log."""
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    ax.set_xlim(0, width_in)
    ax.set_ylim(0, height_in)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.add_patch(Rectangle((0, 0), width_in, height_in, facecolor=background_color, edgecolor="black", linewidth=0.8))
    _draw_hatch(ax, 0, 0, width_in, height_in, pattern_id, angle, size, line_color)
    # io.BytesIO() is an in-memory "file" -- it behaves like a real file
    # you could write bytes to and read back, but the bytes never
    # actually touch disk. matplotlib's savefig can write to it exactly
    # like a real file path, which is what lets this function return the
    # finished PNG's raw bytes directly to its caller (the webapp route,
    # which sends them straight back as an HTTP response) without ever
    # needing to create and then clean up a temporary file on disk.
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    # plt.close(fig) releases the figure's memory. matplotlib keeps every
    # created figure alive in the background until you explicitly close
    # it (in case you wanted to keep drawing on it later) -- forgetting
    # this in a function that gets called repeatedly (like this one,
    # once per thumbnail refresh) is a classic way to slowly leak memory
    # over a long-running process's lifetime.
    plt.close(fig)
    return buf.getvalue()


def _draw_stratigraphy_column(ax, pit: TrialPit, scale: float, templates: list[UnitTemplate]) -> None:
    """Draws the main event of the whole page: the true-to-scale soil
    column down the left side, plus everything that hangs off it -- the
    per-layer dimension lines, depth labels, unit descriptions, the
    groundwater symbol, and the termination caption at the bottom.

    This function works in two clearly separate passes, and the "why" is
    important: PASS 1 (just below) computes *where* every layer's true
    boundaries fall on the page and feeds that to place_descriptions, so
    the whole description stack can be laid out and reflowed as a unit
    (see description_layout.py) before a single pixel is drawn. PASS 2
    (further down) then actually draws everything, now that both the
    column geometry *and* the final description layout are fully known.
    Trying to draw layer-by-layer in one pass instead wouldn't work: a
    layer's description block can end up needing to push text belonging
    to a *later* layer, so the full picture has to be solved first.
    """
    total_depth = pit.total_depth_in
    ax.plot([COLUMN_X - 0.4, MAIN_ZONE_RIGHT], [FRAME_TOP_Y, FRAME_TOP_Y], color="black", linewidth=0.8)
    ax.text(COLUMN_X - 0.4, FRAME_TOP_Y + 0.06, "EXISTING GRADE LEVEL", fontsize=6.5, va="bottom", ha="left")

    if total_depth <= 0:
        # No layers recorded yet for this pit -- draw just the empty
        # frame (a zero-height rectangle, which still shows as the grade
        # line and column edges) rather than crashing on the division
        # that would follow from a zero total depth.
        ax.add_patch(Rectangle((COLUMN_X, FRAME_TOP_Y), COLUMN_W, 0, fill=False, edgecolor="black"))
        return

    col_bottom_y = y_at_depth(FRAME_TOP_Y, scale, total_depth)

    # PASS 1, part A: true-scale y-bounds for every layer, needed up front so the
    # description stack can be laid out as a whole before anything is drawn.
    bands: list[tuple[float, float]] = []
    cumulative = Decimal(0)
    for layer in pit.layers:
        cum_before = cumulative
        cumulative += layer.thickness_in
        bands.append(band_y_range(FRAME_TOP_Y, scale, cum_before, cumulative))

    # PASS 1, part B: package each layer's true position plus its text
    # into a DescriptionUnit (see description_layout.py) and hand the
    # whole list to place_descriptions in one go, so it can see every
    # unit at once while deciding how to reflow them.
    #
    # ADVANCED TECHNIQUE -- zip() and enumerate() together:
    # `zip(pit.layers, bands)` walks through pit.layers and bands *in
    # lockstep*, handing back matched pairs -- (pit.layers[0], bands[0]),
    # then (pit.layers[1], bands[1]), and so on -- as if the two separate
    # lists were one combined list of pairs. Wrapping that in enumerate()
    # additionally numbers each pair (0, 1, 2, ...) as `i`, which is only
    # needed here to work out is_first/is_last (whether this is the very
    # first or very last layer in the pit). The nested unpacking `(layer,
    # (y_top, y_bot))` immediately pulls each pair, and each pair's
    # y_top/y_bot, into their own named variables in one line.
    description_units = [
        DescriptionUnit(
            slot_top=y_top,
            slot_bot=y_bot,
            name=layer.name,
            description=layer.description,
            is_last=(i == len(pit.layers) - 1),
            is_first=(i == 0),
        )
        for i, (layer, (y_top, y_bot)) in enumerate(zip(pit.layers, bands))
    ]
    # frame_bottom is raised by TERMINATION_RESERVED_HEIGHT rather than
    # passing FRAME_BOTTOM_Y directly -- as far as place_descriptions'
    # own push-down/push-up/shrink logic is concerned, the floor of the
    # page is this much higher than FRAME_BOTTOM_Y actually is, so the
    # last unit's landing can never end up so low that the termination
    # caption drawn just below it (see below) would have nowhere left to
    # go before running into the general notes box.
    placed_descriptions = place_descriptions(
        description_units,
        frame_top=FIGURE_TOP_Y,
        frame_bottom=FRAME_BOTTOM_Y + TERMINATION_RESERVED_HEIGHT,
        wrap_width=DESC_WRAP_WIDTH,
        min_gap_ratio=DESC_MIN_GAP_RATIO,
        padding_ratio=DESC_PADDING_RATIO,
        fontsize_default=DESC_FONTSIZE_DEFAULT,
    )

    # PASS 2: now that every layer's position and final text layout are
    # both known, actually draw everything, one layer at a time, top to
    # bottom. zip() here lines up three separate lists (layers, their
    # y-bounds, and their solved description placements) so each loop
    # iteration has everything it needs for one complete layer.
    cumulative = Decimal(0)
    for layer, (y_top, y_bot), placed in zip(pit.layers, bands, placed_descriptions):
        cumulative += layer.thickness_in
        template = find_template(layer.name, templates)
        ax.add_patch(
            Rectangle(
                (COLUMN_X, y_bot),
                COLUMN_W,
                y_top - y_bot,
                facecolor=template.background_color if template else "none",
                edgecolor="black",
                linewidth=0.8,
            )
        )
        if template is not None and template.hatch_pattern != "none":
            _draw_hatch(
                ax,
                COLUMN_X,
                y_bot,
                COLUMN_W,
                y_top - y_bot,
                template.hatch_pattern,
                template.hatch_angle,
                template.hatch_size,
                template.line_color,
            )

        # Per-layer thickness dimension (vertical line, arrows if thick enough).
        _draw_layer_dimension(ax, y_top, y_bot, layer.thickness_in)

        # Accumulated depth landing at this unit's base (last unit == termination depth).
        _draw_depth_landing(ax, y_bot, cumulative)

        # Unit description, reflowed independently of the true-scale column.
        _draw_description_connector(ax, COLUMN_X + COLUMN_W, y_bot, placed.landing_y, placed.fontsize)
        _draw_description_block(ax, placed)

    ax.add_patch(
        Rectangle(
            (COLUMN_X, col_bottom_y),
            COLUMN_W,
            FRAME_TOP_Y - col_bottom_y,
            fill=False,
            edgecolor="black",
            linewidth=1.0,
        )
    )

    if pit.groundwater_depth_in is not None:
        gw_depth = min(pit.groundwater_depth_in, total_depth)
        gw_y = y_at_depth(FRAME_TOP_Y, scale, gw_depth)
        _draw_groundwater_symbol(ax, gw_y, pit, scale)

    # Termination caption: sits directly under the *last* unit
    # description's own landing line, left-aligned with the description
    # text itself at LABEL_X, drawn at that same unit's final placed
    # fontsize -- so it reads as a natural continuation of the
    # description stack rather than a separately-styled caption. This is
    # guaranteed to have room (see TERMINATION_RESERVED_HEIGHT above,
    # which reserved exactly this space before place_descriptions ever
    # laid anything out) regardless of how the last unit's landing ended
    # up positioned.
    last_placed = placed_descriptions[-1]
    ax.text(
        LABEL_X,
        last_placed.landing_y - TERMINATION_TEXT_GAP,
        _termination_caption(pit),
        fontsize=last_placed.fontsize,
        va="top",
        ha="left",
    )


def _fmt(value: str) -> str:
    """Fallback text for any blank project-info field, so an unfilled
    field on the drawing reads as a deliberate "-" placeholder rather
    than an oddly empty gap."""
    return value if value else "-"


def _wrap_lines(text: str, width: int) -> str:
    """Word-wrap each already-newline-separated line independently, so a numbered
    list stays one bullet per visual paragraph instead of merging together.

    textwrap.wrap on its own treats an entire block of text as one long
    paragraph and doesn't know anything about the newlines already inside
    it -- given "1) First note.\\n2) Second note." it would happily merge
    those two numbered points back together if they were short enough to
    fit on one wrapped line. text.splitlines() first breaks the input
    apart at each existing newline, wraps *each piece separately*, then
    "\\n".join(...) glues the wrapped pieces back together -- so a blank
    line survives as a blank line (via the `if line else ""` check,
    since textwrap.wrap on an empty string returns an empty list, not a
    list containing one empty string), and note 1 can never accidentally
    run into note 2."""
    return "\n".join(
        "\n".join(textwrap.wrap(line, width=width)) if line else ""
        for line in text.splitlines()
    )


def _draw_general_notes(ax, project: Project, pit: TrialPit) -> None:
    """The "NOTES:" box at the bottom-left of the page: standard
    boilerplate sentences with a few project-specific blanks filled in
    (equipment, date, file reference, groundwater, whether this pit struck
    true bedrock -- see _bedrock_note), plus one optional extra note
    appended as its own numbered point."""
    text = GENERAL_NOTES_BOILERPLATE.format(
        equipment_note=_equipment_note(project.info, template="TRIAL PIT EXCAVATED WITH A {equipment} SUPPLIED BY {equipment_provider}."),
        date=_fmt(project.info.site_work_completion_date).upper(),
        file_ref=_fmt(project.info.file_ref).upper(),
        groundwater_note=_groundwater_note(pit, verb="DURING"),
        bedrock_note=_bedrock_note(pit),
    )
    if pit.extra_note:
        text += f"\n{len(text.splitlines()) + 1}) {pit.extra_note}"
    text = _wrap_lines(text, width=105)
    draw_box(
        ax, MARGIN, MARGIN, MAIN_ZONE_RIGHT - MARGIN, GENERAL_NOTES_HEIGHT, "NOTES:", text,
        fontsize=GENERAL_NOTES_FONTSIZE, linespacing=GENERAL_NOTES_LINESPACING,
    )


@lru_cache(maxsize=8)
def _load_rgb_image(path: Path) -> np.ndarray:
    """Load an image as RGB, converting CMYK source files (common from Adobe export
    tools) via their embedded ICC profile rather than letting matplotlib misread the
    raw C/M/Y/K channels as R/G/B/A -- that reinterpretation is what made the AMR logo
    render washed-out and under-saturated.

    @lru_cache means this whole function only actually runs once per
    distinct `path` -- every later call with that same path returns the
    same already-decoded array straight from memory instead of re-reading
    the file and redoing the CMYK->sRGB conversion. This matters because
    render_pit_page calls this once per *pit*, so a project with many pits
    would otherwise pay this cost (a disk read plus an ICC profile
    transform) again for every single pit, on every single render -- pure
    repeated work, since the logo file never changes mid-run. Safe to
    share the same cached array across every caller because nothing here
    ever modifies it after loading (ax.imshow only ever reads it).
    """
    img = Image.open(path)
    if img.mode == "CMYK":
        icc_bytes = img.info.get("icc_profile")
        if icc_bytes:
            src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_bytes))
            srgb_profile = ImageCms.createProfile("sRGB")
            img = ImageCms.profileToProfile(img, src_profile, srgb_profile, outputMode="RGB")
        else:
            img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return np.array(img)


def _draw_title_block(
    ax, project: Project, pit: TrialPit | None, cfg: Config, *, title_text: str | None = None, include_notes: bool = True
) -> None:
    """The stack of labelled boxes down the right side of the page (NOTES,
    PROJECT, TITLE, DRAWN BY, SCALE, FILE, and the logo) -- drawn one
    explicit draw_box() call at a time, stacking each box directly below
    the previous one from the top of the page down. NOTES and PROJECT are
    sized to soak up whatever vertical space is left over after the
    fixed-height boxes and the logo have taken their share (see
    remaining_height/notes_h/project_h below). Each box's fontsize and
    linespacing is its own named constant (see TITLE_BLOCK_*_FONTSIZE/
    LINESPACING near the top of this file) rather than a value shared
    across boxes, so any one box's text density can be tuned on its own.

    `title_text`/`include_notes` exist for the Trial Pit Location Plan
    cover sheet (see render_location_plan_page), which reuses this same
    title block styling but with a fixed title instead of a per-pit one
    and no NOTES box at all (its per-pit groundwater/equipment wording
    doesn't make sense for a project-level page) -- `pit` is only ever
    read for that default title and for NOTES, so it's None there."""
    page_h = cfg.page_size_in[1]
    top_y = page_h - MARGIN
    x = TITLE_BLOCK_X
    w = TITLE_BLOCK_W

    if include_notes:
        notes_text = TITLE_BLOCK_NOTES_BOILERPLATE.format(
            equipment_note=_equipment_note(project.info, template="TRIAL PITS EXCAVATED WITH A {equipment}."),
            date=_fmt(project.info.site_work_completion_date).upper(),
            file_ref=_fmt(project.info.file_ref).upper(),
            groundwater_note=_groundwater_note(pit, verb="THROUGHOUT"),
            wall_stability_note=_wall_stability_note(pit),
        )
        notes_text = _wrap_lines(notes_text, width=48)
    project_text = _wrap_lines(
        "\n".join(filter(None, [project.info.project_name, project.info.street_address, project.info.block_and_parcel])) or "-",
        width=38,
    )
    if title_text is None:
        title_text = f"TRIAL PIT NO. {pit.number}"
    drawn_by_text = project.info.drawn_by
    scale_text = project.info.scale_note
    file_text = _fmt(project.info.file_ref)

    # Fixed-height boxes -- each holds one short, unwrapped value rather
    # than a paragraph, so its height doesn't need to depend on the text
    # inside it the way NOTES/PROJECT's heights do below.
    title_h = 0.5
    drawn_by_h = 0.5
    scale_h = 0.5
    file_h = 0.5
    logo_h = 0.9

    bottom_y = MARGIN
    available_height = top_y - bottom_y
    remaining_height = available_height - title_h - drawn_by_h - scale_h - file_h - logo_h
    # No NOTES box -> PROJECT alone soaks up the space that would
    # otherwise have been split between the two of them.
    notes_h = max(remaining_height * 0.5, 1.0) if include_notes else 0.0
    project_h = max(remaining_height - notes_h, 1.0)

    # Walk down from the top of the page, placing each box directly below
    # the previous one -- `y -= height` before drawing means each box's
    # top edge sits exactly where the previous box's bottom edge was.
    y = top_y
    if include_notes:
        y -= notes_h
        draw_box(ax, x, y, w, notes_h, "NOTES:", notes_text, fontsize=TITLE_BLOCK_NOTES_FONTSIZE, linespacing=TITLE_BLOCK_NOTES_LINESPACING)
    y -= project_h
    draw_box(ax, x, y, w, project_h, "PROJECT:", f"GEOTECHNICAL INVESTIGATION\n{project_text.upper()}", fontsize=TITLE_BLOCK_PROJECT_FONTSIZE, linespacing=TITLE_BLOCK_PROJECT_LINESPACING)
    y -= title_h
    draw_box(ax, x, y, w, title_h, "TITLE:", title_text, fontsize=TITLE_BLOCK_TITLE_FONTSIZE, linespacing=TITLE_BLOCK_TITLE_LINESPACING)
    y -= drawn_by_h
    draw_box(ax, x, y, w, drawn_by_h, "DRAWN BY:", drawn_by_text, fontsize=TITLE_BLOCK_DRAWN_BY_FONTSIZE, linespacing=TITLE_BLOCK_DRAWN_BY_LINESPACING)
    y -= scale_h
    draw_box(ax, x, y, w, scale_h, "SCALE:", scale_text, fontsize=TITLE_BLOCK_SCALE_FONTSIZE, linespacing=TITLE_BLOCK_SCALE_LINESPACING)
    y -= file_h
    draw_box(ax, x, y, w, file_h, "FILE:", file_text, fontsize=TITLE_BLOCK_FILE_FONTSIZE, linespacing=TITLE_BLOCK_FILE_LINESPACING)

    y -= logo_h
    ax.add_patch(Rectangle((x, y), w, logo_h, fill=False, edgecolor="black", linewidth=0.8))
    if cfg.logo_path and Path(cfg.logo_path).exists():
        img = _load_rgb_image(cfg.logo_path)
        pad = 0.08
        box_w, box_h = w - 2 * pad, logo_h - 2 * pad
        img_aspect = img.shape[1] / img.shape[0]
        # Fit the logo within the box preserving its aspect ratio (rather than stretching to fill
        # it) -- this is a fixed company logo now, not an arbitrary user upload, so it needs to
        # look correct on every render.
        if img_aspect > box_w / box_h:
            fit_w, fit_h = box_w, box_w / img_aspect
        else:
            fit_h, fit_w = box_h, box_h * img_aspect
        fit_x = x + (w - fit_w) / 2
        fit_y = y + (logo_h - fit_h) / 2
        ax.imshow(img, extent=(fit_x, fit_x + fit_w, fit_y, fit_y + fit_h), aspect="auto", zorder=5)
    else:
        ax.text(x + w / 2, y + logo_h / 2, cfg.company_name, fontsize=8, fontweight="bold", va="center", ha="center")

    # Outer border around the whole title block column -- see
    # TITLE_BLOCK_BORDER_LINEWIDTH above for why this is bolder than the
    # plain Rectangle every box inside it uses.
    ax.add_patch(
        Rectangle(
            (x, y),
            w,
            top_y - y,
            fill=False,
            edgecolor="black",
            linewidth=TITLE_BLOCK_BORDER_LINEWIDTH,
        )
    )


def _draw_page_border(ax, cfg: Config) -> None:
    """The plain outer page frame every page gets, regardless of what
    else is (or isn't) drawn inside it -- shared by render_pit_page and
    render_location_plan_page."""
    ax.add_patch(
        Rectangle(
            (MARGIN, MARGIN),
            cfg.page_size_in[0] - 2 * MARGIN,
            cfg.page_size_in[1] - 2 * MARGIN,
            fill=False,
            edgecolor="black",
            linewidth=PAGE_BORDER_LINEWIDTH,
        )
    )


def render_pit_page(fig, ax, project: Project, pit: TrialPit, cfg: Config, scale: float, templates: list[UnitTemplate]) -> None:
    """Assembles one complete page for one pit: the outer page border,
    then the three major regions (stratigraphy column, general notes,
    title block), each delegated to its own _draw_xxx function above.
    `fig` is accepted alongside `ax` purely so this function's signature
    mirrors _new_axes's (fig, ax) return pair -- everything actually
    drawn here goes through `ax`, since matplotlib artists are added to
    an axes, not a figure, directly."""
    _draw_page_border(ax, cfg)
    _draw_stratigraphy_column(ax, pit, scale, templates)
    _draw_general_notes(ax, project, pit)
    _draw_title_block(ax, project, pit, cfg)


def render_location_plan_page(fig, ax, project: Project, cfg: Config) -> None:
    """Assembles the Trial Pit Location Plan cover sheet: the plain page
    border and a project-level version of the title block (see
    _draw_title_block's title_text/include_notes) -- no stratigraphy
    column, no general notes box. Deliberately leaves the rest of the
    page blank: this app has no site-plan/coordinate data to draw an
    actual pit-location map from, so the page is meant to be finished by
    hand afterward, the same "manually-completed page" pattern Appendix A
    ("Site Figures") already uses elsewhere in this report package."""
    _draw_page_border(ax, cfg)
    _draw_title_block(ax, project, None, cfg, title_text="TRIAL PIT LOCATION PLAN", include_notes=False)


def compute_project_scale(project: Project) -> float:
    """The one shared scale every pit's page must be drawn at (see
    layout.py's compute_scale_preferring_fixed): whichever pit is deepest
    decides it, so every pit's column ends up visually comparable on the
    same true-to-life scale. Prefers FIXED_COLUMN_SCALE (a real,
    nameable, "1 inch = 2 feet" scale) whenever the deepest pit fits
    within COLUMN_HEIGHT_BUDGET at it, only falling back to zooming to
    exactly fill the frame for a pit too deep for that fixed scale to fit
    on the page -- see compute_scale_preferring_fixed's own docstring for
    why (a shallow pit shouldn't get stretched to fill the whole page
    just for being the deepest thing in its own project).

    Pulled out of render_project into its own function so a caller that
    renders one pit's page at a time -- render_pit_pdf below, used by the
    webapp's live-edit preview -- can compute this same whole-project
    value without duplicating the "deepest pit wins" logic, and without
    needing to actually render every other pit first."""
    max_depth = max((pit.total_depth_in for pit in project.pits), default=Decimal(0))
    return compute_scale_preferring_fixed(max_depth, COLUMN_HEIGHT_BUDGET, FIXED_COLUMN_SCALE)


def render_pit_pdf(
    project: Project, pit: TrialPit, cfg: Config, scale: float,
    templates: list[UnitTemplate], output_path: str | Path,
) -> None:
    """Render exactly one pit's page to its own single-page PDF file --
    everything render_project's per-pit loop does for one iteration, but
    standalone rather than appended into one shared multi-page PDF.

    This exists for the webapp's live-edit preview: editing one unit's
    description only ever changes that one pit's own page, so re-drawing
    every other pit too (which is what calling render_project again would
    do) is pure wasted work that gets slower the more pits a project has.
    Rendering just the changed pit here, then merging pre-rendered pages
    back into the combined PDF (see webapp/app.py), keeps a live edit's
    cost independent of how many other pits exist.

    `scale` must be the same value used for every other pit in the
    project (see compute_project_scale above) -- passing it in rather
    than recomputing it here is what keeps this pit's column drawn at the
    same scale as its neighbors, even though this function never looks at
    those neighbors itself."""
    fig, ax = _new_axes(cfg)
    render_pit_page(fig, ax, project, pit, cfg, scale, templates)
    fig.savefig(output_path)
    plt.close(fig)


def render_location_plan_pdf(project: Project, cfg: Config, output_path: str | Path) -> None:
    """Renders the Trial Pit Location Plan cover sheet (see
    render_location_plan_page) to its own single-page PDF -- one per
    project, not one per pit, since it's just the title block on an
    otherwise blank page, independent of any individual pit's own data."""
    fig, ax = _new_axes(cfg)
    render_location_plan_page(fig, ax, project, cfg)
    fig.savefig(output_path)
    plt.close(fig)


def render_project(
    project: Project,
    output_path: str | Path,
    cfg: Config | None = None,
    templates: list[UnitTemplate] | None = None,
) -> None:
    """The top-level entry point for this whole module -- the function
    every caller (the CLI's `build` command, the webapp's /generate
    route) actually calls to turn a Project into a finished multi-page
    PDF at output_path.

    Both `cfg` and `templates` are optional: `cfg or Config()` supplies
    the standard page/branding defaults if the caller didn't provide
    their own Config, and `load_catalog() if templates is None else
    templates` similarly loads the on-disk catalog if the caller didn't
    already have one loaded -- letting most callers just write
    render_project(project, "out.pdf") while still letting a caller that
    already loaded the catalog for another reason (like the webapp, which
    also uses it for hydrate_descriptions) pass it in once and skip a
    redundant second disk read.
    """
    cfg = cfg or Config()
    templates = load_catalog() if templates is None else templates
    # Every pit on every page must share one scale (see layout.py's
    # compute_scale) so depths are visually comparable across pits --
    # that's why the scale is computed once here, from whichever pit is
    # deepest, rather than separately inside the per-pit loop below.
    scale = compute_project_scale(project)
    # ADVANCED TECHNIQUE -- a context manager (the `with` statement):
    # PdfPages manages a single open PDF file that pages get appended to
    # one at a time. Using `with PdfPages(output_path) as pdf:` guarantees
    # the file is properly finished and closed (writing the PDF's final
    # table-of-contents-like structure) once this block ends -- including
    # if an error happens partway through -- without needing an explicit
    # try/finally to make sure `pdf.close()` always runs. This is the
    # same "automatically clean up when you're done, even on error"
    # pattern as opening a file with `with open(...) as f:`.
    with PdfPages(output_path) as pdf:
        for pit in project.pits:
            fig, ax = _new_axes(cfg)
            render_pit_page(fig, ax, project, pit, cfg, scale, templates)
            pdf.savefig(fig)
            # Close each page's figure right after it's saved into the
            # PDF, rather than waiting until the whole project is done --
            # a project with many pits would otherwise keep every single
            # page's full-resolution figure in memory simultaneously.
            plt.close(fig)
