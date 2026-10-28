from decimal import Decimal

from pypdf import PdfReader

from tp_drawer.config import Config
from tp_drawer.drawing import (
    NOTES_FONTSIZE_FLOOR,
    _fit_box_text,
    _notes_line_height_in,
    compute_project_scale,
    render_pit_pdf,
)
from tp_drawer.excel_io import read_project
from tp_drawer.models import Layer, Project, ProjectInfo, TrialPit

from .conftest import DEFAULT_HEADER, make_workbook


def test_fit_box_text_keeps_default_fontsize_when_text_already_fits():
    text = "1) A SHORT NOTE.\n2) ANOTHER SHORT NOTE."
    lines, fontsize = _fit_box_text(text, wrap_width=105, fontsize_default=6.8, available_height=1.0)

    assert fontsize == 6.8
    assert lines == ["1) A SHORT NOTE.", "2) ANOTHER SHORT NOTE."]


def test_fit_box_text_shrinks_fontsize_so_long_text_fits_a_small_box():
    # Boilerplate-sized text plus a long extra_note, the same shape a real
    # NOTES box renders -- see _draw_general_notes -- squeezed into a box
    # far too short for it at the default fontsize.
    text = "\n".join(f"{i}) ITEM NUMBER {i} OF THE NOTES BOILERPLATE TEXT." for i in range(1, 7))
    available_height = 0.3  # much shorter than 6 lines at the default fontsize

    lines, fontsize = _fit_box_text(text, wrap_width=105, fontsize_default=6.8, available_height=available_height)

    assert fontsize < 6.8
    # The actual guarantee this function exists to provide: whatever
    # fontsize it settles on, the text it returns genuinely fits.
    assert len(lines) * _notes_line_height_in(fontsize) <= available_height + 1e-9


def test_fit_box_text_guarantees_fit_even_for_an_extremely_long_note():
    # A pathological case -- a very long pasted-in extra_note -- squeezed
    # into the general notes box's real fixed height, to confirm the
    # "no fixed floor, some small enough fontsize always fits" guarantee
    # (see NOTES_FONTSIZE_FLOOR/NOTES_SHRINK_FACTOR's own comments, which
    # mirror description_layout.py's identical guarantee for descriptions).
    boilerplate = "\n".join(f"{i}) BOILERPLATE ITEM {i}." for i in range(1, 7))
    long_note = "VERY LONG PASTED-IN TEXT. " * 80
    text = f"{boilerplate}\n7) {long_note}"
    available_height = 1.3 - 0.11 - 0.15  # GENERAL_NOTES_HEIGHT minus the label's own reserved space

    lines, fontsize = _fit_box_text(text, wrap_width=105, fontsize_default=6.8, available_height=available_height)

    assert len(lines) * _notes_line_height_in(fontsize) <= available_height + 1e-9
    assert fontsize > NOTES_FONTSIZE_FLOOR  # found a genuine fit, didn't just hit the safety floor


def test_fit_box_text_rewraps_wider_as_fontsize_shrinks():
    # _fit_box_text rescales the character wrap width at each smaller
    # fontsize it tries (via description_layout.scaled_wrap_width) so a
    # smaller font actually uses the freed-up horizontal room, rather
    # than shrinking the font while leaving needlessly short lines.
    text = "ONE VERY LONG UNBROKEN SENTENCE " * 10
    lines, fontsize = _fit_box_text(text, wrap_width=20, fontsize_default=6.8, available_height=0.05)

    assert fontsize < 6.8
    assert max(len(line) for line in lines) > 20


def test_render_pit_pdf_does_not_crash_with_an_extremely_long_extra_note(tmp_path):
    # End-to-end smoke test mirroring the pure-function tests above:
    # a real pit with a huge extra_note still renders a valid one-page
    # PDF rather than raising or producing a broken file.
    workbook_path = tmp_path / "input.xlsx"
    make_workbook(
        workbook_path,
        DEFAULT_HEADER,
        pit_numbers=[1],
        layers=[("Topsoil\n(Layer thickness)", ["3'-5\""])],
        groundwater=[None],
    )
    project = read_project(workbook_path)
    project.pits[0].extra_note = "A VERY LONG SUPPLEMENTARY NOTE THAT KEEPS GOING. " * 40

    output_path = tmp_path / "pit_0.pdf"
    render_pit_pdf(project, project.pits[0], Config(), compute_project_scale(project), [], output_path)

    assert output_path.exists()
    reader = PdfReader(str(output_path))
    assert len(reader.pages) == 1


def _mixed_case_project() -> Project:
    """A minimal Project/TrialPit with every free-text field this test
    file cares about deliberately set to mixed/lower case, the way a
    user would actually type them into the input spreadsheet or the web
    UI's click-to-edit popup -- not the all-caps convention the drawing
    itself is supposed to enforce."""
    info = ProjectInfo(
        project_name="dilbert home",
        drawn_by="mam",
        scale_note="n.t.s.",
        file_ref="amr15412",
        equipment="mini excavator",
        equipment_provider="amr rentals ltd.",
    )
    pit = TrialPit(
        number="1",
        layers=[Layer(name="Topsoil", thickness_in=Decimal(24), description="Dark brown sandy topsoil.")],
        termination_reason="ironshore formation marl",
        extra_note="a lowercase supplementary note added by the engineer.",
    )
    return Project(info=info, pits=[pit])


def test_drawing_forces_free_text_fields_to_uppercase(tmp_path):
    # Covers every gap this fix closes: extra_note (_draw_general_notes),
    # drawn_by/scale_note/file_ref (_draw_title_block), and
    # termination_reason (_termination_caption). Reads the rendered PDF's
    # actual text (not the Python strings that fed it) so this fails if
    # the fix is ever accidentally reverted.
    project = _mixed_case_project()
    output_path = tmp_path / "pit_0.pdf"
    render_pit_pdf(project, project.pits[0], Config(), compute_project_scale(project), [], output_path)

    page_text = PdfReader(str(output_path)).pages[0].extract_text()

    mixed_case_originals = [
        "a lowercase supplementary note added by the engineer.",
        "mam",
        "n.t.s.",
        "amr15412",
        "ironshore formation marl",
    ]
    for original in mixed_case_originals:
        assert original not in page_text, f"found un-uppercased text on the drawing: {original!r}"

    uppercase_expected = [
        "A LOWERCASE SUPPLEMENTARY NOTE ADDED BY THE ENGINEER.",
        "MAM",
        "N.T.S.",
        "AMR15412",
        "IRONSHORE FORMATION MARL",
    ]
    for expected in uppercase_expected:
        assert expected in page_text, f"expected all-caps text not found on the drawing: {expected!r}"
