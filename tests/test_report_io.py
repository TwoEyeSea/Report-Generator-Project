from decimal import Decimal

from tp_drawer.catalog import load_foundation_catalog
from tp_drawer.models import Layer, Project, ProjectInfo, TrialPit
from tp_drawer.report_io import _foundation_context, _notes_context


def _project_with_notes(*notes: str) -> Project:
    info = ProjectInfo(project_name="Dilbert Home")
    pits = [
        TrialPit(
            number=str(i + 1),
            layers=[Layer(name="Topsoil", thickness_in=Decimal(24), description="Topsoil.")],
            extra_note=note,
        )
        for i, note in enumerate(notes)
    ]
    return Project(info=info, pits=pits)


def test_notes_context_preserves_mixed_case_extra_note_verbatim():
    # Regression guard: tp_drawer.drawing now deliberately upper-cases
    # extra_note for the trial pit log drawing (see
    # _draw_general_notes), but the Word report body must keep it
    # exactly as the user typed it -- see this function's own docstring
    # and the project's note that the two outputs are independent reads
    # of the same underlying field, not a shared formatted string.
    #
    # Two pits, only one with a note (and the other's blank) -- this is
    # what actually exercises the per-pit "TP{number}: ..." branch below;
    # every pit sharing one identical note instead takes the "All Tps:"
    # branch (see test_notes_context_all_pits_identical_still_preserves_case).
    project = _project_with_notes("a lowercase note the engineer typed, with Mixed Case too.", "")

    context = _notes_context(project)

    assert context["notes_lines"] == ["TP1: a lowercase note the engineer typed, with Mixed Case too."]


def test_notes_context_all_pits_identical_still_preserves_case():
    project = _project_with_notes("same Note on Every pit.", "same Note on Every pit.")

    context = _notes_context(project)

    assert context == {"notes_heading": "All Tps:", "notes_lines": ["same Note on Every pit."]}


def _project_recommending(*foundation_names: str) -> Project:
    info = ProjectInfo(project_name="Dilbert Home", recommended_foundations=list(foundation_names))
    return Project(info=info, pits=[])


def test_foundation_catalog_has_a_pilasters_entry_with_real_boilerplate():
    # The real, on-disk catalog (data/foundation_catalog.json), not a
    # fixture -- this is the actual data file an engineer's "Pilasters"
    # recommendation on the input sheet resolves against.
    options = load_foundation_catalog()
    names = [option.name for option in options]
    assert "Pilasters" in names

    pilasters = next(o for o in options if o.name == "Pilasters")
    assert pilasters.plain_paragraphs
    assert "pilaster" in pilasters.plain_paragraphs[0].lower()


def test_foundation_context_resolves_pilasters_case_insensitively():
    # "pilasters" typed in lowercase on the input sheet (see
    # catalog._find_by_name's forgiving matching) must still resolve to
    # the real write-up, not the "[No stored write-up ...]" placeholder
    # _foundation_section_for falls back to for an unrecognised name.
    project = _project_recommending("pilasters")
    options = load_foundation_catalog()

    context = _foundation_context(project, options)

    section = context["foundation_sections"][0]
    assert section.heading_text == "Recommended Foundation: pilasters"
    assert section.plain_paragraphs
    assert "No stored write-up" not in section.plain_paragraphs[0]
