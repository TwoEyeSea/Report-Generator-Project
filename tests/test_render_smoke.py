from pypdf import PdfReader

from tp_drawer.catalog import UnitTemplate
from tp_drawer.drawing import render_project
from tp_drawer.excel_io import read_project

from .conftest import DEFAULT_HEADER, make_workbook


def test_render_project_produces_expected_page_count(tmp_path):
    workbook_path = tmp_path / "input.xlsx"
    make_workbook(
        workbook_path,
        DEFAULT_HEADER,
        pit_numbers=[1, 2, 3],
        layers=[
            ("Topsoil\n(Layer thickness)", ["3'-5\"", "3'-10\"", "3'-10\""]),
            ("Peat\n(Layer thickness)", ["1'-10\"", "1'-3\"", "1'-7\""]),
            ("Beach Sand\n(Layer thickness)", ["2'-1\"", "1'-9\"", "1'-4\""]),
        ],
        groundwater=["7'-2\"", "4'-11\"", "6'-5\""],
    )
    project = read_project(workbook_path)

    output_path = tmp_path / "output.pdf"
    render_project(project, output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0

    reader = PdfReader(str(output_path))
    assert len(reader.pages) == 3


def test_render_project_draws_hatch_patterns_for_cataloged_units(tmp_path):
    workbook_path = tmp_path / "input.xlsx"
    make_workbook(
        workbook_path,
        DEFAULT_HEADER,
        pit_numbers=[1],
        layers=[
            ("Clay\n(Layer thickness)", ["3'-5\""]),
            ("Gravel\n(Layer thickness)", ["2'-0\""]),
        ],
        groundwater=[None],
    )
    project = read_project(workbook_path)
    templates = [
        UnitTemplate(name="Clay", hatch_pattern="dashes", hatch_angle=30.0, hatch_size=0.8, background_color="#cbb994", line_color="#3a2f1c"),
        UnitTemplate(name="Gravel", hatch_pattern="circles", hatch_angle=0.0, hatch_size=1.2, background_color="none", line_color="black"),
    ]

    output_path = tmp_path / "output.pdf"
    render_project(project, output_path, templates=templates)

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_render_project_handles_pit_with_no_groundwater(tmp_path):
    workbook_path = tmp_path / "input.xlsx"
    make_workbook(
        workbook_path,
        DEFAULT_HEADER,
        pit_numbers=[1],
        layers=[("Topsoil\n(Layer thickness)", ["3'-5\""])],
        groundwater=[None],
    )
    project = read_project(workbook_path)

    output_path = tmp_path / "output.pdf"
    render_project(project, output_path)

    assert output_path.exists()
