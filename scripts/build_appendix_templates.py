"""Builds data/appendix_{a,b,c,d}_template.docx from the reference
appendix documents in reference/Templates/ -- same docxtpl/Jinja2 tagging
approach as build_report_template.py (see that file's own module
docstring for the general rationale). Run whenever a source appendix
document is revised:
    python scripts/build_appendix_templates.py

Appendix A ("Site Figures") and Appendix C ("Trial Pit Logs") are pure
title/divider pages with no body content at all: tag the shared header
(project number + a numeric date) and leave the rest untouched, aside
from forcing every title-page paragraph to TITLE_PAGE_FONT_SIZE (see
below).

Appendix D ("Limitations") has a real body -- generic legal boilerplate
with no project-specific wording anywhere in it -- so it gets its own
title page too: a hard page break (same technique as Appendix B's, see
_insert_page_break) right after the "LIMITATIONS" title heading pushes
the document's own boilerplate heading/text onto page 2 instead of it
running on immediately below the title on page 1.

Every appendix's title page gets every one of its (non-header/footer)
paragraphs forced to an explicit TITLE_PAGE_FONT_SIZE (see
set_font_size): the source documents mix explicitly-large heading text
with blank spacer paragraphs that carry NO explicit size at all, and it's
that inconsistency -- not any one paragraph being simply "wrong" -- that
was throwing the title pages' layout off.

Appendix B ("Photographic Record") is the one with the most real work to
do: its photo-gallery tables get rebuilt into two docxtpl row loops (one
per trial pit's Dug/Spoils photos, one for however many extra site photos
got uploaded) so it scales to any project instead of the fixed
4-pit/14-photo example layout -- see tp_drawer/photo_gallery_io.py for
how those loops' data gets built and rendered.
"""

from pathlib import Path

import docx
from docx.enum.text import WD_BREAK

from _docx_tagging_utils import (
    clear_picture_run,
    clone_row,
    clone_run_after,
    collapse_blank_paragraphs,
    drop_unused_images,
    insert_paragraph_after,
    remove_intervening_paragraphs,
    set_default_font,
    set_font_size,
    set_tag,
    set_tag_after_marker,
)

TITLE_PAGE_FONT_SIZE = 24

SOURCE_DIR = Path(__file__).resolve().parent.parent / "reference" / "Templates"
DEST_DIR = Path(__file__).resolve().parent.parent / "data"

DEFAULT_FONT = "Roboto"

# (source filename, destination filename) for each appendix.
_SOURCES = {
    "a": "APPENDIX A.docx",
    "b": "APPENDIX B - Photo Gallery neo.docx",
    "c": "APPENDIX C.docx",
    "d": "APPENDIX D.docx",
}

# (heading text, subtitle text) for the two-line title every appendix
# opens with -- used by _position_title_lines_7_and_8 below. Appendix D's
# "LIMITATIONS" subtitle is deliberately the SAME text as its own body
# heading further down the document; _position_title_lines_7_and_8 always
# matches the FIRST paragraph with that exact text, which is this title
# line since it comes first in document order.
_TITLE_TEXT = {
    "a": ("APPENDIX A", "SITE FIGURES"),
    "c": ("APPENDIX C", "TRIAL PIT LOGS"),
    "d": ("APPENDIX D", "LIMITATIONS"),
}


def _position_title_lines_7_and_8(d: docx.Document, heading_text: str, subtitle_text: str) -> None:
    """Positions an appendix's two-line title -- "APPENDIX X" on line 7,
    its subtitle directly on line 8 beneath it -- the shape confirmed
    with the user for Appendix B (see the older, since-generalized
    comment this replaced), now applied to every appendix since they all
    share the identical "6 blank lines, heading, 1 blank, subtitle" shape
    in their own source documents.

    Must run AFTER collapse_blank_paragraphs (every caller here already
    calls it first), which reduces that leading run of 6 blanks down to
    1 -- this restores the 5 that got collapsed away, and drops the
    single blank that separated the heading from its subtitle so the two
    land on directly consecutive lines. The newly inserted blanks carry
    no explicit font size of their own -- callers are expected to force
    one over every title-page paragraph (including these) right after
    calling this."""
    parent = d.paragraphs[0]._parent
    heading = next(p for p in d.paragraphs if p.text.strip() == heading_text)
    subtitle = next(p for p in d.paragraphs if p.text.strip() == subtitle_text)
    remove_intervening_paragraphs(heading._p, subtitle._p)
    preceding = heading._p.getprevious()  # the single leading blank collapse left behind
    for _ in range(5):
        preceding = insert_paragraph_after(preceding, parent)._p


def _tag_header(d: docx.Document) -> None:
    """Tags every appendix's shared header pattern:
    "APPENDIX X\\t\\tAMR 15483" -> "...\\t\\t{{ project_number }}", and a
    numeric date paragraph -> "{{ report_date_numeric }}" wholesale.

    set_tag_after_marker (rather than a fixed run index) is needed here
    because "AMR" lands in a different run, sometimes fused with a
    leading tab, in each of the four source files -- Word's own edit
    history fragments runs unpredictably even for visually-identical
    text, so anchoring on the *substring* rather than a run index is what
    makes one function work unmodified across all four files.
    """
    header = d.sections[0].header
    header_paras = [p for p in header.paragraphs if p.text.strip()]
    # header_paras[0]: "APPENDIX X\t\tAMR 15483" -- keep "APPENDIX X\t\t" static.
    set_tag_after_marker(header_paras[0], "AMR", "{{ project_number }}")
    # header_paras[1]: the numeric date, e.g. "08/09/2026" -- wholesale tag.
    set_tag(header_paras[1], 0, "{{ report_date_numeric }}")


def _build_simple(name: str) -> None:
    """Appendix A/C: header tagging, position the title on lines 7/8 (see
    _position_title_lines_7_and_8), then force every (non-header/footer)
    paragraph -- the whole document is just a title/divider page -- to
    TITLE_PAGE_FONT_SIZE."""
    d = docx.Document(SOURCE_DIR / _SOURCES[name])
    _tag_header(d)
    set_default_font(d, DEFAULT_FONT)
    collapse_blank_paragraphs(d)
    _position_title_lines_7_and_8(d, *_TITLE_TEXT[name])
    for p in d.paragraphs:
        set_font_size(p, TITLE_PAGE_FONT_SIZE)
    dest = DEST_DIR / f"appendix_{name}_template.docx"
    d.save(dest)
    print(f"Wrote {dest}")


def _build_appendix_d() -> None:
    """Appendix D ("Limitations") gets its own title page, like every
    other appendix: title on lines 7/8 (see _position_title_lines_7_and_8;
    "LIMITATIONS" here matches the FIRST paragraph with that exact text --
    the title, not the document's own body heading further down that
    repeats it), then a hard page break right after that title subtitle
    line pushes the body heading and all the boilerplate legal text after
    it onto page 2, instead of running on immediately below the title on
    page 1. Only the title page's own paragraphs (before the break) get
    forced to TITLE_PAGE_FONT_SIZE -- the body content keeps its own
    existing (smaller) heading/paragraph sizes, since the user's request
    was about the title pages specifically, not the legal text itself."""
    d = docx.Document(SOURCE_DIR / _SOURCES["d"])
    _tag_header(d)
    set_default_font(d, DEFAULT_FONT)
    collapse_blank_paragraphs(d)
    _position_title_lines_7_and_8(d, *_TITLE_TEXT["d"])

    parent = d.paragraphs[0]._parent
    body_paras = d.paragraphs
    title_subtitle = next(p for p in body_paras if p.text.strip() == "LIMITATIONS")
    for p in body_paras[: body_paras.index(title_subtitle) + 1]:
        set_font_size(p, TITLE_PAGE_FONT_SIZE)
    _insert_page_break(title_subtitle._p, parent)

    dest = DEST_DIR / "appendix_d_template.docx"
    d.save(dest)
    print(f"Wrote {dest}")


def _tag_photo_run(photo_para, condition_expr: str, value_expr: str) -> None:
    """Paragraph 0 of a photo-gallery cell holds the picture (a single
    run with a <w:drawing>, no text -- see clear_picture_run). `{% if %}`
    (not the {%p %}/{%tr %} paragraph/row scoped tags) is right here
    because this is an ordinary inline substitution within one run, not
    something that needs to remove or repeat a wrapping XML element --
    when condition_expr is falsy, the run's text renders empty rather
    than raising, leaving the photo area blank for the engineer to fill
    in by hand later. condition_expr and value_expr are the same
    expression for a pit's own Dug/Spoils photo (e.g. "pit.dug_photo"),
    but differ for an extra photo's row slot, where the *slot itself*
    (e.g. "row.left") is what can be None, not the .photo attribute on
    an object that doesn't exist."""
    clear_picture_run(photo_para.runs[0])
    set_tag(photo_para, 0, f"{{% if {condition_expr} %}}{{{{ {value_expr} }}}}{{% endif %}}")


def _tag_caption_cell(cell, number_expr: str, rest_expr: str, *, guard: str | None = None) -> None:
    """A photo's caption paragraph becomes two runs -- a bold "Photo N"
    tag, then a non-bold " - filename" tag -- rather than one, so Word
    renders the number in bold and the filename plain. Both expressions
    are plain strings computed in Python (photo_gallery_io.py), already
    "" when there's no photo for this slot, so a missing pit photo's
    caption is just a blank line with no {% if %} of its own needed here.
    `guard`, when given, wraps *both* runs in the same {% if %} -- needed
    for an extra photo's row slot, where the slot itself (not just its
    caption fields) can be None."""
    caption_para = cell.paragraphs[-1]
    number_tag = f"{{{{ {number_expr} }}}}"
    rest_tag = f"{{{{ {rest_expr} }}}}"
    if guard:
        number_tag = f"{{% if {guard} %}}{number_tag}{{% endif %}}"
        rest_tag = f"{{% if {guard} %}}{rest_tag}{{% endif %}}"
    set_tag(caption_para, 0, number_tag, bold=True)
    clone_run_after(caption_para.runs[0], rest_tag, bold=False)


def _make_page_break(paragraph) -> None:
    """Turns an (empty) paragraph into a hard page break -- a real
    <w:br w:type="page"/>, not a paragraph property -- so it can be
    wrapped in a {%p if %} block to make it conditional on which loop
    iteration is rendering (see _insert_conditional_break)."""
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)
    paragraph.add_run().add_break(WD_BREAK.PAGE)


def _insert_marker(anchor_element, parent, text: str):
    """Inserts a new paragraph holding a plain Jinja control tag (e.g.
    "{%p for page in pit_pages %}") immediately after `anchor_element` (a
    <w:p> or <w:tbl>). Returns the new paragraph's own element, so calls
    can be chained (each next insertion anchored on the previous one)."""
    p = insert_paragraph_after(anchor_element, parent)
    set_tag(p, 0, text)
    return p._p


def _insert_page_break(anchor_element, parent):
    """Inserts a new hard-page-break paragraph immediately after
    `anchor_element`. Returns the new paragraph's own element."""
    p = insert_paragraph_after(anchor_element, parent)
    _make_page_break(p)
    return p._p


def _insert_conditional_break(anchor_element, parent, condition: str):
    """Appends, in order, right after `anchor_element`: a
    "{%p if condition %}" marker, a hard page break, and a "{%p endif %}"
    marker. Returns the last element, for further chaining. Used both for
    "break between pages within one loop" (condition references
    loop.last) and "break between the pit-photos and extra-photos
    sections" (condition is the plain has_extras flag)."""
    el = _insert_marker(anchor_element, parent, f"{{%p if {condition} %}}")
    el = _insert_page_break(el, parent)
    return _insert_marker(el, parent, "{%p endif %}")


def _build_appendix_b() -> None:
    """Appendix B's photo gallery is rebuilt around a simple rule (per
    the user's own simplification): the title stays alone on its own
    page regardless of photo count, and every subsequent page holds up
    to 4 photos -- one small 2-row table per page, 2 photos per row, a
    hard page break between one page's table and the next. Both the
    per-pit Dug/Spoils photos and the "extra" site photos use the exact
    same 2-rows-of-2-photos-per-page shape; report_io.py's
    photo_gallery_io.py does the actual chunking into pages (`pit_pages`,
    `extra_pages`) so this template only ever needs a fixed 2-row table
    per section, never a variable-length row loop."""
    d = docx.Document(SOURCE_DIR / _SOURCES["b"])
    _tag_header(d)
    set_default_font(d, DEFAULT_FONT)
    parent = d.paragraphs[0]._parent

    body_paras = d.paragraphs
    tables = d.tables

    # ---- Title page: nothing else shares it, regardless of photo count ----
    title_heading = next(p for p in body_paras if p.text.strip() == "PHOTOGRAPHIC RECORD")
    for p in body_paras[: body_paras.index(title_heading) + 1]:
        set_font_size(p, TITLE_PAGE_FONT_SIZE)
    el = _insert_page_break(title_heading._p, parent)
    el = _insert_marker(el, parent, "{%p for page in pit_pages %}")
    # The source document's own long run of blank spacer paragraphs
    # originally sat between the heading and table 0 -- now sitting
    # between this for-marker and table 0, which would otherwise get
    # needlessly repeated once per rendered page.
    remove_intervening_paragraphs(el, tables[0]._tbl)

    # ---- Per-pit "page" table: table 0's own 2 rows become page.row1/ ----
    # row2 (up to 2 pits' worth -- 4 photos -- per page; a page with only
    # 1 pit left over has page.row2 be None, per photo_gallery_io.py's
    # chunking). Both rows already have the right per-cell shape (image
    # paragraph + caption paragraph) except row1 (misleadingly the
    # *second* row in the source table, since page.row1 reuses whichever
    # row already had the simpler shape), which carries an extra leading
    # blank paragraph the other doesn't -- dropped so both match.
    pit_table = tables[0]
    page_row1, page_row2 = pit_table.rows[0], pit_table.rows[1]
    for cell in page_row2.cells:
        leading_blank = cell.paragraphs[0]
        leading_blank._p.getparent().remove(leading_blank._p)
    pit_table.rows[2]._tr.getparent().remove(pit_table.rows[2]._tr)  # old trailing spacer row

    _tag_photo_run(page_row1.cells[0].paragraphs[0], "page.row1.dug_photo", "page.row1.dug_photo")
    _tag_caption_cell(page_row1.cells[0], "page.row1.dug_caption_number", "page.row1.dug_caption_rest")
    _tag_photo_run(page_row1.cells[1].paragraphs[0], "page.row1.spoils_photo", "page.row1.spoils_photo")
    _tag_caption_cell(page_row1.cells[1], "page.row1.spoils_caption_number", "page.row1.spoils_caption_rest")
    # A blank trailing paragraph in each row1 cell visually separates the
    # top row of photos from the bottom row within the same page's table
    # (per the user's explicit request) -- appended AFTER tagging, not
    # before, so _tag_caption_cell's own cell.paragraphs[-1] lookup still
    # finds the real caption paragraph, not this new blank one.
    for cell in page_row1.cells:
        cell.add_paragraph()

    # page.row2 as a whole may be None (an odd pit count's last page) --
    # every guard below checks that first, short-circuiting before ever
    # reaching into a None's own attributes.
    _tag_photo_run(page_row2.cells[0].paragraphs[0], "page.row2 and page.row2.dug_photo", "page.row2.dug_photo")
    _tag_caption_cell(page_row2.cells[0], "page.row2.dug_caption_number", "page.row2.dug_caption_rest", guard="page.row2")
    _tag_photo_run(page_row2.cells[1].paragraphs[0], "page.row2 and page.row2.spoils_photo", "page.row2.spoils_photo")
    _tag_caption_cell(page_row2.cells[1], "page.row2.spoils_caption_number", "page.row2.spoils_caption_rest", guard="page.row2")

    # ---- Drop the old fixed pit3/4 table and the fixed Boulder table ----
    # entirely -- both are subsumed by the per-pit pages above (any pit
    # count) and the extra-photos pages below (Boulder shots are just
    # ordinary uploaded extras now, captioned from their own filename).
    for old_table in (tables[1], tables[2]):
        old_table._tbl.getparent().remove(old_table._tbl)

    # ---- Page break between pages of pit photos, then (only if there ----
    # are any) another before the extra-photos section.
    el = _insert_conditional_break(pit_table._tbl, parent, "not loop.last")
    el = _insert_marker(el, parent, "{%p endfor %}")
    el = _insert_conditional_break(el, parent, "has_extras")
    el = _insert_marker(el, parent, "{%p for page in extra_pages %}")
    remove_intervening_paragraphs(el, tables[3]._tbl)

    # ---- Extra-photos "page" table: same 2-row-per-page shape, using ----
    # the old Branch/Excavator table's own single row as page.row1 and a
    # clone of it as page.row2 (that table never had a second row).
    extra_table = tables[3]
    page_row1 = extra_table.rows[0]
    page_row2_tr = clone_row(page_row1, before=False)
    page_row2 = next(r for r in extra_table.rows if r._tr is page_row2_tr)

    for row, row_name, guard in ((page_row1, "row1", None), (page_row2, "row2", "page.row2")):
        for cell, side in ((row.cells[0], "left"), (row.cells[1], "right")):
            slot = f"page.{row_name}.{side}"
            photo_condition = slot if guard is None else f"{guard} and {slot}"
            _tag_photo_run(cell.paragraphs[0], photo_condition, f"{slot}.photo")
            _tag_caption_cell(cell, f"{slot}.caption_number", f"{slot}.caption_rest", guard=photo_condition)
        if row_name == "row1":
            # Same top/bottom row separator as the per-pit table above.
            for cell in row.cells:
                cell.add_paragraph()

    el = _insert_conditional_break(extra_table._tbl, parent, "not loop.last")
    _insert_marker(el, parent, "{%p endfor %}")

    # Every one of the example's 14 embedded photos has now had its
    # <w:drawing> reference stripped -- drop the now-fully-unreferenced
    # image parts too, or ~1.5MB of dead example photos would sit in
    # every file generated from this template.
    drop_unused_images(d)
    # The source document's own remaining long runs of blank spacer
    # paragraphs (between table 0 and where tables 1/2 used to be) are
    # what originally caused the page-spread bug this whole section-break
    # redesign replaced -- still worth collapsing regardless, as a
    # general cleanup of leftover authoring cruft.
    collapse_blank_paragraphs(d)

    # ---- Title position: "APPENDIX B" on line 7, "PHOTOGRAPHIC RECORD" ----
    # directly on line 8 beneath it (both centered, via the existing
    # "Heading 9" style -- untouched here) -- per the user's explicit
    # request, now the same shape every other appendix's title gets via
    # _position_title_lines_7_and_8. Not sharing that helper here since
    # this call happens well after this function's own collapse_blank_
    # paragraphs (further table/photo restructuring sits in between,
    # unlike the other appendices) -- same net effect, different spot in
    # the function. collapse_blank_paragraphs above just reduced the
    # source document's own leading run of 6 blank paragraphs down to 1
    # (and left the single blank between the two heading lines as-is,
    # already at the 1-paragraph floor) -- restore exactly what's needed:
    # 6 blanks before the first heading line, and none between the two.
    title_line1 = next(p for p in d.paragraphs if p.text.strip() == "APPENDIX B")
    title_line2 = next(p for p in d.paragraphs if p.text.strip() == "PHOTOGRAPHIC RECORD")
    remove_intervening_paragraphs(title_line1._p, title_line2._p)
    preceding = title_line1._p.getprevious()  # the single leading blank collapse left behind
    for _ in range(5):
        new_p = insert_paragraph_after(preceding, parent)
        # A freshly inserted paragraph carries no explicit size at all --
        # matching every other title-page paragraph's forced size here is
        # what the earlier set_font_size pass on the *original* leading
        # blanks (now collapsed away) would otherwise have guaranteed.
        set_font_size(new_p, TITLE_PAGE_FONT_SIZE)
        preceding = new_p._p

    dest = DEST_DIR / "appendix_b_template.docx"
    d.save(dest)
    print(f"Wrote {dest}")


def build() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("a", "c"):
        _build_simple(name)
    _build_appendix_d()
    _build_appendix_b()


if __name__ == "__main__":
    build()
