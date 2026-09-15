"""Shared helpers for scripting docxtpl/Jinja2 tags into a real Word
document -- used by both build_report_template.py and
build_appendix_templates.py. See build_report_template.py's own
module docstring for the general rationale (why this is scripted rather
than hand-edited in Word, why every tag lands in a single run).
"""

import copy

from docx.enum.text import WD_COLOR_INDEX
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph


def set_tag(paragraph: Paragraph, start_run_index: int, text: str, *, bold: bool | None = None) -> None:
    """Collapse paragraph.runs[start_run_index:] into a single run holding
    `text` (typically a Jinja tag like "{{ client }}"), deleting every run
    after it. Runs *before* start_run_index (e.g. a bold "Label: " prefix
    that should stay put) are left completely alone.

    If start_run_index is past the end of the existing runs (e.g. the
    paragraph has no runs at all -- a blank spacer paragraph being reused
    as a tag's anchor, which happens more than once in this project), a
    brand new run is appended instead -- and explicitly given this
    project's one and only font, Roboto (see set_default_font), for
    exactly the reason clone_run_after's own docstring explains: a run
    with no rFonts of its own falls back to its PARAGRAPH STYLE's own
    default font, not to whatever font the visually-surrounding text
    happens to use -- and at least one of this document's own styles
    defaults to a completely different font (Univers), which is what
    silently produced the wrong-font bug this fixes.
    """
    runs = paragraph.runs
    if start_run_index < len(runs):
        base = runs[start_run_index]
        base.text = text
        if bold is not None:
            base.bold = bold
        for extra in runs[start_run_index + 1 :]:
            extra._element.getparent().remove(extra._element)
    else:
        new_run = paragraph.add_run(text)
        new_run.font.name = "Roboto"
        if bold is not None:
            new_run.bold = bold


def set_tag_after_marker(paragraph: Paragraph, marker: str, text: str, *, bold: bool | None = None) -> None:
    """Like set_tag, but finds the run to start collapsing from by
    locating `marker`'s starting position within the paragraph's
    concatenated text, rather than a known run index -- useful when a
    static prefix and the part that becomes a tag are fused into the same
    run (Word's own edit history fragments runs unpredictably, so which
    run a given substring starts in varies file to file even for
    visually-identical text). The run containing marker's start is
    truncated to just its text *before* the marker (kept as-is, static);
    everything from the marker onward (that run's own remainder, plus any
    further runs) is discarded and replaced by set_tag's usual single-run
    collapse.
    """
    runs = paragraph.runs
    full_text = "".join(r.text for r in runs)
    marker_pos = full_text.index(marker)
    pos = 0
    for i, run in enumerate(runs):
        run_len = len(run.text)
        if pos <= marker_pos < pos + run_len:
            run.text = run.text[: marker_pos - pos]
            set_tag(paragraph, i + 1, text, bold=bold)
            return
        pos += run_len
    raise ValueError(f"marker {marker!r} not found in paragraph text {full_text!r}")


def clear_cell(cell) -> None:
    """Blank out every paragraph in a table cell down to a single empty
    run -- used on the rows we clone to carry a bare {%tr %} marker tag,
    so none of the original row's data text (or, via clear_picture_run,
    any embedded picture -- Run.text's setter only ever adds/updates a
    <w:t>, it never touches a <w:drawing>, so a cloned picture-bearing run
    would otherwise still carry its image even after this) leaks into the
    output."""
    for paragraph in cell.paragraphs:
        runs = paragraph.runs
        if runs:
            clear_picture_run(runs[0])
            runs[0].text = ""
            for extra in runs[1:]:
                extra._element.getparent().remove(extra._element)


def insert_paragraph_after(anchor_element, parent) -> Paragraph:
    """Creates a new, empty paragraph immediately after `anchor_element`
    and returns it wrapped as a python-docx Paragraph. `addnext` works on
    any lxml element regardless of type, so `anchor_element` can be
    another <w:p> or a <w:tbl> -- unlike python-docx's own
    Paragraph.insert_paragraph_before, which only ever works before a
    *paragraph*, this project needs to place marker/page-break paragraphs
    directly after a *table* used as a docxtpl loop body, which that
    method can't do. `parent` should be an existing paragraph's own
    `._parent` (e.g. `document.paragraphs[0]._parent`) -- the same object
    python-docx itself passes when constructing any other top-level
    Paragraph."""
    new_p = OxmlElement("w:p")
    anchor_element.addnext(new_p)
    return Paragraph(new_p, parent)


def remove_intervening_paragraphs(start_element, end_element) -> None:
    """Deletes every top-level <w:p> sitting strictly between
    `start_element` and `end_element` (exclusive of both, and regardless
    of what kind of element `end_element` is -- a table works fine as a
    stopping point, not just another paragraph). Used to clear leftover
    spacer paragraphs out of a docxtpl {%p for %} loop's own span so they
    don't get needlessly repeated once per iteration -- e.g. when the
    loop's own for-marker paragraph is inserted right after a heading,
    but the table that's meant to be the very next thing in the loop
    body sits several old spacer paragraphs further down the document."""
    node = start_element.getnext()
    while node is not None and node is not end_element:
        following = node.getnext()
        if node.tag == qn("w:p"):
            node.getparent().remove(node)
        node = following


def clone_run_after(run, text: str, *, bold: bool | None = None):
    """Insert a new run immediately after `run`, cloning `run`'s own rPr
    (font, size, language, etc.) rather than starting from python-docx's
    Paragraph.add_run(), which creates a run with NO explicit run
    properties at all. That matters here: a run with no rPr doesn't
    render invisibly or "inherit visually the same as its neighbour" --
    Word falls back to the style chain's own default font/size for it,
    which can differ from the surrounding text's *explicit* formatting
    (e.g. this document's body text is explicitly set to a particular
    font+size per run, not via the style's own defaults). Two adjacent
    runs with silently different effective formatting is also exactly
    what makes Word report "mixed" values (Font.Size == 9999999) when
    anything measures the paragraph as a whole -- cloning the neighbour's
    actual rPr avoids that class of bug entirely, not just the visual
    mismatch.

    Returns the new run, with `.text` already set to `text` and `.bold`
    overridden if given (everything else stays exactly as cloned)."""
    new_element = copy.deepcopy(run._element)
    run._element.addnext(new_element)
    new_run = type(run)(new_element, run._parent)
    new_run.text = text
    if bold is not None:
        new_run.bold = bold
    return new_run


def clear_picture_run(run) -> None:
    """Remove a run's embedded picture (<w:drawing>), if it has one,
    leaving the run otherwise intact -- needed before turning a picture-
    only run into a docxtpl InlineImage tag via set_tag: python-docx's
    Run.text setter only ever adds/updates a <w:t> child, it never removes
    a <w:drawing> child, so simply setting .text on a picture run would
    leave the tag text sitting *alongside* the original static image
    rather than replacing it."""
    drawing = run._element.find(qn("w:drawing"))
    if drawing is not None:
        run._element.remove(drawing)


def set_list_level(paragraph: Paragraph, ilvl: int) -> None:
    """Change which level of its multilevel list a heading paragraph sits
    at (e.g. moving it from a "X.Y.Z"-numbered level to a "X.Y"-numbered
    one) by editing its <w:numPr><w:ilvl w:val="..."/> in place. Word
    computes the visible number (e.g. "3.1") from this plus the document's
    numbering.xml level definitions, not from anything docxtpl or this
    script writes as text -- so this is the only way to fix a
    mis-leveled heading."""
    numPr = paragraph._element.find(f".//{qn('w:numPr')}")
    if numPr is None:
        raise ValueError(f"Paragraph {paragraph.text!r} has no numPr to change the list level of.")
    ilvl_el = numPr.find(qn("w:ilvl"))
    ilvl_el.set(qn("w:val"), str(ilvl))


def add_list_numbering(paragraph: Paragraph, ilvl: int, numId: int) -> None:
    """Give a paragraph that has NO existing numPr a real Word multilevel-
    list auto-number (as opposed to set_list_level above, which edits one
    that's already there). Word then computes "5.1", "5.2", ... from the
    document's actual structure, so it can't drift out of sync the way a
    hand-typed number would if the document is later restructured.

    get_or_add_pPr/get_or_add_numPr/get_or_add_ilvl/get_or_add_numId are
    python-docx's own oxml accessors -- they insert each new element at
    the schema-correct position among any existing siblings, which hand-
    building this XML by hand would risk getting wrong."""
    pPr = paragraph._p.get_or_add_pPr()
    numPr = pPr.get_or_add_numPr()
    numPr.get_or_add_ilvl().val = ilvl
    numPr.get_or_add_numId().val = numId


def highlight_yellow(paragraph: Paragraph) -> None:
    """Marks every run in a paragraph with Word's yellow text highlight --
    e.g. used on the main report's Conclusion section to visually flag it
    as project-sensitive content that needs the engineer's review. Applied
    to a {%p %}/{%tr %} loop body paragraph, this survives being cloned
    once per loop iteration, same as bold/other run formatting."""
    for run in paragraph.runs:
        run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def _get_or_add_paragraph_mark_rPr(pPr):
    """The <w:rPr> that hangs directly off <w:pPr> (as opposed to any
    run's own <w:rPr>) formats the paragraph MARK itself -- the invisible
    "end of paragraph" character -- which is what actually determines a
    *blank* paragraph's line height, since a blank paragraph has no runs
    of its own for a size to live on. python-docx has no get_or_add_rPr()
    for CT_PPr (unlike get_or_add_numPr/get_or_add_ind), so this inserts
    it by hand at the schema-correct position: immediately before
    w:sectPr/w:pPrChange if either is present (both always sort after
    w:rPr per the CT_PPr schema), otherwise as the last child."""
    rPr = pPr.find(qn("w:rPr"))
    if rPr is not None:
        return rPr
    rPr = OxmlElement("w:rPr")
    successor = pPr.find(qn("w:sectPr"))
    if successor is None:
        successor = pPr.find(qn("w:pPrChange"))
    if successor is not None:
        successor.addprevious(rPr)
    else:
        pPr.append(rPr)
    return rPr


def set_font_size(paragraph: Paragraph, points: int) -> None:
    """Forces an explicit font size onto every run in `paragraph` AND its
    paragraph mark (see _get_or_add_paragraph_mark_rPr above) -- used on
    the appendix title pages, whose source documents carry a mix of
    explicitly-sized text and blank spacer paragraphs with NO explicit
    size at all (falling back to whatever tiny default the viewer
    supplies). It's that inconsistency in spacer-paragraph line heights
    sitting right next to explicitly-large heading text -- not any one
    paragraph being wrong on its own -- that throws off a title page's
    layout, so every paragraph on the page needs the same explicit size,
    not just the ones that already had text."""
    for run in paragraph.runs:
        run.font.size = Pt(points)
    mark_rPr = _get_or_add_paragraph_mark_rPr(paragraph._p.get_or_add_pPr())
    sz = mark_rPr.find(qn("w:sz"))
    if sz is None:
        sz = OxmlElement("w:sz")
        mark_rPr.append(sz)
    sz.set(qn("w:val"), str(points * 2))


def clone_row(anchor_row, *, before: bool):
    """Clone `anchor_row`'s XML (so the new row has the same cell count/
    widths/formatting) and insert it immediately before or after the
    anchor row. Returns the new row's underlying <w:tr> element (not a
    wrapper object -- the caller re-reads table.rows to get a fresh,
    correctly-indexed one)."""
    new_tr = copy.deepcopy(anchor_row._tr)
    if before:
        anchor_row._tr.addprevious(new_tr)
    else:
        anchor_row._tr.addnext(new_tr)
    return new_tr


def collapse_blank_paragraphs(document, max_consecutive: int = 1) -> None:
    """Collapses any run of consecutive blank (no-text) paragraphs
    directly in the document body down to at most `max_consecutive`.

    Every one of this project's reference documents (likely a side
    effect of however they were originally authored/converted -- these
    started life as .doc files) turned out to carry long runs of
    leftover blank paragraphs between sections: as many as 40 in a row
    in one case. Each one still has its own paragraph-mark font size and
    so still consumes real vertical space even though nothing is visibly
    on it -- accumulated across dozens of them, that's easily enough to
    push real content onto extra pages with nothing "wrong" about any
    individual element (confirmed against the actual source document,
    unmodified: Appendix B's example already spanned 5 pages before any
    of this project's own template edits ever touched it). Only ever
    removes *entire* blank paragraphs and never touches one with real
    text, so this can't clip real content -- at most `max_consecutive`
    is always left in place as a visual spacer, never zero.

    A paragraph counts as "blank" only if it has neither text NOR any
    non-text content (a manual page break, a picture) -- Paragraph.text
    only ever reflects <w:t> content, so a paragraph holding nothing but
    a <w:br w:type="page"/> also reports "" for .text despite doing
    real, structural work. Checking for those explicitly is what makes
    this function safe to call even after inserting page-break
    paragraphs of exactly that shape (see build_appendix_templates.py's
    Appendix B section-break logic)."""

    def _is_blank(child) -> bool:
        if child.tag != qn("w:p"):
            return False
        if Paragraph(child, document).text.strip():
            return False
        return child.find(f".//{qn('w:br')}") is None and child.find(f".//{qn('w:drawing')}") is None

    body = document.element.body
    run: list = []
    for child in list(body.iterchildren()):
        is_blank_paragraph = _is_blank(child)
        if is_blank_paragraph:
            run.append(child)
            continue
        for extra in run[max_consecutive:]:
            extra.getparent().remove(extra)
        run = []
    for extra in run[max_consecutive:]:
        extra.getparent().remove(extra)


def set_default_font(document, font_name: str) -> None:
    """Sets the document's actual default font in every place that
    matters -- EVERY named style (not just "Normal", which is merely the
    style any paragraph with no more specific style of its own falls
    back to) and styles.xml's own docDefaults (the ultimate fallback
    below even "Normal", used by a run that has no explicit rFonts and no
    style of its own -- e.g. exactly what Paragraph.add_run()/
    clone_run_after produce before either sets a font).

    Every style beyond "Normal" matters too: several of this project's
    reference documents define their own heading/list/character styles
    (e.g. "21", the outline-heading style used throughout the main
    report) whose OWN font default is something else entirely --
    "Univers", in one confirmed case -- rather than inheriting Normal's.
    A run that relies on ITS OWN paragraph's style for its font rather
    than Normal's (an auto-generated list-number glyph with no font of
    its own in numbering.xml, or a tag anchored on an originally-empty
    paragraph -- see set_tag) silently picks up THAT style's font
    instead, bypassing Normal entirely -- which is exactly how a stray
    Univers heading number/paragraph slipped into an otherwise
    all-Roboto document. LIST-type styles (returned by the loop below
    alongside PARAGRAPH/CHARACTER/TABLE ones) have no .font of their own
    to set, hence the try/except.

    Every one of this project's reference documents had "Normal" set to
    "Times New Roman" -- Roboto is only ever applied per-run via explicit
    rFonts on top of it, so a run that's missing that explicit override
    (as clone_run_after's whole existence guards against) would otherwise
    silently fall through to Times New Roman, not Roboto."""
    for style in document.styles:
        try:
            style.font.name = font_name
        except AttributeError:
            pass

    styles_element = document.styles.element
    rPrDefault = styles_element.find(f".//{qn('w:docDefaults')}/{qn('w:rPrDefault')}/{qn('w:rPr')}")
    if rPrDefault is not None:
        rFonts = rPrDefault.find(qn("w:rFonts"))
        if rFonts is not None:
            for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
                rFonts.set(qn(attr), font_name)


def drop_unused_images(document) -> None:
    """Removes every image relationship (and, since it becomes
    unreachable once its last relationship is dropped, the underlying
    media part itself) that nothing in the document body still points to.

    Needed after clear_picture_run/clear_cell strip a <w:drawing> element
    out of a run: that only removes the *reference* to the picture, not
    the embedded image data itself -- word/media/imageN.jpeg stays in the
    .docx package as dead weight (in one real case, ~1.5MB of leftover
    example photos) unless the now-orphaned relationship is explicitly
    dropped too. Run this once, after all edits, right before saving."""
    body_xml = document.element.xml
    part = document.part
    for rId, rel in list(part.rels.items()):
        if rel.reltype == RT.IMAGE and f'"{rId}"' not in body_xml:
            part.drop_rel(rId)
