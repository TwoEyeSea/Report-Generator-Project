"""Maintained diagnostic (not a one-off): renders a dummy trial pit and
overlays it with labels naming every drawn element after its corresponding
variable/function in the tp_drawer source, so the user and Claude can refer
to elements by their real names in conversation. Not part of the shipped
app -- treat this file as living documentation: whenever a constant it
labels changes name, value, or meaning, regenerate it and check the labels
still match reality.

Run with:  PYTHONPATH=. python reference/annotated_reference.py
"""

from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import tp_drawer.drawing as d
from tp_drawer.config import Config
from tp_drawer.description_layout import DescriptionUnit, place_descriptions
from tp_drawer.layout import band_y_range, compute_scale
from tp_drawer.models import Layer, Project, ProjectInfo, TrialPit

# ---------------------------------------------------------------------------
# Build a small dummy project: 1 pit, 4 layers, chosen so all three
# connector states (_classify() in description_layout.py) show up at once:
#   Topsoil     -- plenty of room, lands exactly on its own slot -> "neutral"
#   Sandy Gravel -- gets nudged up slightly to make room below   -> "up"
#   Peat        -- also nudged up                                -> "up"
#   Stiff Clay  -- is_last, crowded against the boundary         -> "down"
# This is the same variety the original single-purpose version of this
# script aimed for (a thin last layer forcing a "down" connector), extended
# to show "up" and "neutral" too so every connector state is visible in one
# diagram.
# ---------------------------------------------------------------------------
project = Project(
    info=ProjectInfo(
        date="01/01/26", project_number="REF 0001", street_address="Reference Example",
        block_and_parcel="N/A", equipment_provider="N/A", equipment="N/A",
    ),
    pits=[
        TrialPit(
            number="X",
            layers=[
                Layer(name="Topsoil", thickness_in=Decimal(30), description="Dark brown organic silt with roots, moist, loose."),
                Layer(name="Sandy Gravel", thickness_in=Decimal(10), description="Light brown sandy gravel, medium dense, sub-rounded, occasional cobbles."),
                Layer(name="Peat", thickness_in=Decimal(4), description="Dark brown to black fibrous peat, saturated, low density, highly decomposed organic matter throughout, compressible."),
                Layer(name="Stiff Clay", thickness_in=Decimal(4), description="Firm to stiff grey clay with occasional silt partings, moist, low plasticity, some rootlets near top."),
            ],
            groundwater_depth_in=None,
        )
    ],
)
pit = project.pits[0]
cfg = Config()
scale = compute_scale(pit.total_depth_in, d.COLUMN_HEIGHT_BUDGET)

# ---------------------------------------------------------------------------
# Recompute the same per-layer placement drawing.py computes internally
# (matching render_pit_page's own PASS 1 exactly, frame_top/frame_bottom
# included), so the annotations below point at the real numbers that get
# drawn rather than guessed ones.
# ---------------------------------------------------------------------------
cumulative = Decimal(0)
bands = []
for layer in pit.layers:
    cum_before = cumulative
    cumulative += layer.thickness_in
    bands.append(band_y_range(d.FRAME_TOP_Y, scale, cum_before, cumulative))

description_units = [
    DescriptionUnit(slot_top=yt, slot_bot=yb, name=layer.name, description=layer.description, is_last=(i == len(pit.layers) - 1), is_first=(i == 0))
    for i, (layer, (yt, yb)) in enumerate(zip(pit.layers, bands))
]
placed = place_descriptions(
    description_units,
    frame_top=d.FIGURE_TOP_Y,
    frame_bottom=d.FRAME_BOTTOM_Y + d.TERMINATION_RESERVED_HEIGHT,
    wrap_width=d.DESC_WRAP_WIDTH, min_gap_ratio=d.DESC_MIN_GAP_RATIO, padding_ratio=d.DESC_PADDING_RATIO,
    fontsize_default=d.DESC_FONTSIZE_DEFAULT,
)

# ---------------------------------------------------------------------------
# Render the real page content, unmodified, onto a larger canvas so there's
# room around the edges for callouts.
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = cfg.page_size_in
CANVAS_W, CANVAS_H = 20.0, 14.0
X_OFF, Y_OFF = 2.2, 3.0  # where the real page's (0,0) sits within the canvas

fig = plt.figure(figsize=(CANVAS_W, CANVAS_H))
ax = fig.add_axes((0, 0, 1, 1))
ax.set_xlim(0, CANVAS_W)
ax.set_ylim(0, CANVAS_H)
ax.set_aspect("equal")
ax.axis("off")

# Shift everything the real renderer draws by (X_OFF, Y_OFF) using a nested
# transform, so drawing.py's absolute-inch constants land in the right place
# on our larger canvas without modifying drawing.py at all.
inner = fig.add_axes((X_OFF / CANVAS_W, Y_OFF / CANVAS_H, PAGE_W / CANVAS_W, PAGE_H / CANVAS_H))
inner.set_xlim(0, PAGE_W)
inner.set_ylim(0, PAGE_H)
inner.set_aspect("equal")
inner.axis("off")
d.render_pit_page(fig, inner, project, pit, cfg, scale, [])


def to_canvas(x, y):
    return X_OFF + x, Y_OFF + y


ANNOT_COLOR = "#c0392b"
BOX_COLOR = "#2471a3"


def label(text, xy_page, xytext_canvas, color=ANNOT_COLOR, ha="left"):
    xy = to_canvas(*xy_page)
    ax.annotate(
        text, xy=xy, xytext=xytext_canvas, textcoords="data",
        fontsize=8, color=color, ha=ha, va="center",
        arrowprops=dict(arrowstyle="->", color=color, lw=0.9, shrinkA=0, shrinkB=2),
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, lw=0.6),
    )


def dashed_box(x, y, w, h, color=BOX_COLOR):
    cx, cy = to_canvas(x, y)
    ax.add_patch(Rectangle((cx, cy), w, h, fill=False, edgecolor=color, linewidth=1.1, linestyle=(0, (5, 3))))


def hline(x0, x1, y, color=BOX_COLOR):
    cx0, cy = to_canvas(x0, y)
    cx1, _ = to_canvas(x1, y)
    ax.plot([cx0, cx1], [cy, cy], color=color, linewidth=1.0, linestyle=(0, (4, 3)))


def vline(x, y0, y1, color=BOX_COLOR):
    cx0, cy0 = to_canvas(x, y0)
    _, cy1 = to_canvas(x, y1)
    ax.plot([cx0, cx0], [cy0, cy1], color=color, linewidth=1.0, linestyle=(0, (4, 3)))


# ---------------------------------------------------------------------------
# Frame-level structures
# ---------------------------------------------------------------------------
label("MARGIN (outer border)", (d.MARGIN, cfg.page_size_in[1] - d.MARGIN), (0.1, 13.4))
label("FRAME_TOP_Y\n(\"EXISTING GRADE LEVEL\" line;\ntrue-scale column bands are\nmeasured down from here)", (d.COLUMN_X - 0.4, d.FRAME_TOP_Y), (0.1, 12.3))
label("MAIN_ZONE_RIGHT", (d.MAIN_ZONE_RIGHT, d.FRAME_TOP_Y), (14.8, 12.7))
label("_draw_general_notes()\nGENERAL_NOTES_HEIGHT", (d.MARGIN + 2.5, d.MARGIN + 0.65), (0.1, 0.6))
label("_draw_title_block()\n(TITLE_BLOCK_X, TITLE_BLOCK_W)", (d.TITLE_BLOCK_X + 1.4, 5.5), (17.6, 5.0), ha="left")

# The description stack's own push-up/shrink ceiling and floor are NOT
# FRAME_TOP_Y/FRAME_BOTTOM_Y themselves -- place_descriptions is handed
# FIGURE_TOP_Y (a hair above the grade line) and FRAME_BOTTOM_Y raised by
# TERMINATION_RESERVED_HEIGHT (room for the caption below the last
# landing). Drawing both boxes makes that split visible.
dashed_box(d.COLUMN_X - 0.4, d.FRAME_BOTTOM_Y, d.MAIN_ZONE_RIGHT - (d.COLUMN_X - 0.4), d.FRAME_TOP_Y - d.FRAME_BOTTOM_Y, color=BOX_COLOR)
label("figure frame: FRAME_TOP_Y .. FRAME_BOTTOM_Y\n(FRAME_BOTTOM_Y = MARGIN + GENERAL_NOTES_HEIGHT;\nnothing may ever render below this line)", (d.COLUMN_X - 0.4, d.FRAME_BOTTOM_Y), (0.1, 2.2))

raised_bottom = d.FRAME_BOTTOM_Y + d.TERMINATION_RESERVED_HEIGHT
hline(d.COLUMN_X - 0.4, d.MAIN_ZONE_RIGHT, d.FIGURE_TOP_Y, color="#8e44ad")
label("FIGURE_TOP_Y\n(place_descriptions' frame_top;\na little above FRAME_TOP_Y so\nthe grade line sits inside it)", (d.MAIN_ZONE_RIGHT - 0.1, d.FIGURE_TOP_Y), (17.3, 9.7), color="#8e44ad")
hline(d.COLUMN_X - 0.4, d.MAIN_ZONE_RIGHT, raised_bottom, color="#8e44ad")
label(
    "place_descriptions' frame_bottom =\nFRAME_BOTTOM_Y + TERMINATION_RESERVED_HEIGHT\n(reserves room for _termination_caption() below\nthe last landing, so its push-up/shrink loop never\nlets a landing get so low the caption has nowhere to go)",
    (d.MAIN_ZONE_RIGHT - 0.1, raised_bottom), (9.3, 0.9), color="#8e44ad",
)

# ---------------------------------------------------------------------------
# Column / spine structures
# ---------------------------------------------------------------------------
vline(d.COLUMN_X, d.FRAME_BOTTOM_Y + 0.3, d.FRAME_TOP_Y + 0.3)
label("COLUMN_X", (d.COLUMN_X, d.FRAME_TOP_Y + 0.25), (2.8, 13.0))
label("COLUMN_W\n(2'-0\" real, drawn to scale)", (d.COLUMN_X + d.COLUMN_W, bands[0][1]), (4.9, 8.3))
vline(d.DIM_X, d.FRAME_BOTTOM_Y + 0.3, d.FRAME_TOP_Y + 0.3)
label(
    "DIM_X == DESC_SPINE_X\n(shared spine: _draw_layer_dimension,\n_draw_depth_landing, and\n_draw_description_connector all start here)",
    (d.DIM_X, d.FRAME_TOP_Y + 0.25), (6.3, 13.4),
)
vline(d.LABEL_X, d.FRAME_BOTTOM_Y + 0.3, d.FRAME_TOP_Y + 0.3)
label("LABEL_X\n(_draw_description_block\ntext starts here)", (d.LABEL_X, d.FRAME_TOP_Y + 0.25), (9.6, 13.4))

# ---------------------------------------------------------------------------
# Per-layer annotations -- one block per DescriptionUnit, showing its true
# slot (purple, on the column) and where place_descriptions actually put
# its text and landing (green), including which of the three connector
# states (_classify()) it ended up as.
# ---------------------------------------------------------------------------
LAYER_LABEL_Y = [10.4, 8.6, 6.9, 5.6]
CONNECTOR_LABEL_Y = [11.0, 8.9, 6.6, 4.3]
for i, (layer, (y_top, y_bot), p) in enumerate(zip(pit.layers, bands, placed)):
    dashed_box(d.COLUMN_X, y_bot, d.COLUMN_W, y_top - y_bot, color="#7d3c98")
    label(
        f"Layer(name={layer.name!r})\nDescriptionUnit.slot_top={y_top:.2f}\nDescriptionUnit.slot_bot={y_bot:.2f}",
        (d.COLUMN_X, (y_top + y_bot) / 2), (0.1, LAYER_LABEL_Y[i]), ha="left", color="#7d3c98",
    )
    label(
        f"PlacedDescription: connector={p.connector!r}\nblock_top_y={p.block_top_y:.2f}  landing_y={p.landing_y:.2f}\nfontsize={p.fontsize:.2f}",
        (d.LABEL_X + 2.55, p.block_top_y - 0.15), (13.9, CONNECTOR_LABEL_Y[i]),
        ha="left", color="#1e8449",
    )

# One fully-labeled example (Peat, index 2) of the two distinct DIM_X-side
# elements, plus the description connector itself.
peat_top, peat_bot = bands[2]
label("_draw_layer_dimension()\n(thickness dimension line)", (d.DIM_X, (peat_top + peat_bot) / 2), (0.1, 4.4), color="#b9770e")
label("_draw_depth_landing()\n(accumulated-depth tick)", (d.DIM_X, peat_bot), (0.1, 3.4), color="#b9770e")
label("_draw_description_connector()\n(tick + diagonal to LABEL_X --\nflat when connector='neutral'/'flat',\nsloped when 'up'/'down')", (d.DESC_SPINE_X, (peat_top + peat_bot) / 2 - 0.3), (5.2, 1.6), color="#117864")

# ---------------------------------------------------------------------------
# Termination caption -- the text drawn directly under the *last* unit's
# landing line, in the space TERMINATION_RESERVED_HEIGHT reserved for it.
# ---------------------------------------------------------------------------
last_placed = placed[-1]
label(
    "_termination_caption(pit) text\n(drawn at LABEL_X, last_placed.landing_y\n- TERMINATION_TEXT_GAP, at last_placed.fontsize)",
    (d.LABEL_X + 1.6, last_placed.landing_y - d.TERMINATION_TEXT_GAP - 0.05), (12.6, 2.6), color="#b03a2e",
)

ax.text(CANVAS_W / 2, CANVAS_H - 0.35, "Annotated reference -- object names as they appear in tp_drawer source", fontsize=11, fontweight="bold", ha="center")

out_dir = Path("reference")
out_dir.mkdir(exist_ok=True)
pdf_path = out_dir / "annotated_reference_v2.pdf"
fig.savefig(pdf_path)
print(f"wrote {pdf_path}")

# Also drop a PNG next to it for quick viewing without a PDF reader.
try:
    import pymupdf

    doc = pymupdf.open(pdf_path)
    png_path = out_dir / "annotated_reference_v2.png"
    doc[0].get_pixmap(dpi=150).save(png_path)
    doc.close()
    print(f"wrote {png_path}")
except ImportError:
    pass
