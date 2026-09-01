from decimal import Decimal

from tp_drawer.catalog import UnitTemplate, find_template, hydrate_descriptions, load_catalog, save_catalog
from tp_drawer.models import Layer, Project, ProjectInfo, TrialPit


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "catalog.json"
    templates = [UnitTemplate(name="Topsoil", description="Dark brown organic silt."), UnitTemplate(name="Peat", description="Fibrous, saturated.")]
    save_catalog(templates, path)

    loaded = load_catalog(path)

    assert loaded == templates


def test_load_missing_file_returns_empty_list(tmp_path):
    assert load_catalog(tmp_path / "does_not_exist.json") == []


def test_hatch_fields_roundtrip_through_save_and_load(tmp_path):
    path = tmp_path / "catalog.json"
    templates = [
        UnitTemplate(
            name="Clay",
            description="Firm brown clay.",
            hatch_pattern="dashes",
            hatch_angle=45.0,
            hatch_size=1.5,
            background_color="#cbb994",
            line_color="#3a2f1c",
        )
    ]
    save_catalog(templates, path)

    assert load_catalog(path) == templates


def test_hatch_fields_default_when_missing_from_stored_json(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text('[{"name": "Topsoil", "description": "Old entry saved before hatch fields existed."}]')

    loaded = load_catalog(path)

    assert loaded == [
        UnitTemplate(
            name="Topsoil",
            description="Old entry saved before hatch fields existed.",
            hatch_pattern="none",
            hatch_angle=0.0,
            hatch_size=1.0,
            background_color="none",
            line_color="black",
        )
    ]


def test_find_template_is_case_insensitive():
    templates = [UnitTemplate(name="Beach Sand", description="Loose, fine, tan.")]

    assert find_template("beach sand", templates) is templates[0]
    assert find_template("BEACH SAND", templates) is templates[0]
    assert find_template("Gravel", templates) is None


def test_hydrate_descriptions_copies_matching_template_text():
    templates = [UnitTemplate(name="Topsoil", description="Dark brown organic silt.")]
    layer = Layer(name="Topsoil", thickness_in=Decimal(12))
    project = Project(info=ProjectInfo(), pits=[TrialPit(number="1", layers=[layer])])

    hydrate_descriptions(project, templates)

    assert layer.description == "Dark brown organic silt."


def test_hydrate_descriptions_does_not_overwrite_existing_text():
    templates = [UnitTemplate(name="Topsoil", description="Template text.")]
    layer = Layer(name="Topsoil", thickness_in=Decimal(12), description="Already edited by the user.")
    project = Project(info=ProjectInfo(), pits=[TrialPit(number="1", layers=[layer])])

    hydrate_descriptions(project, templates)

    assert layer.description == "Already edited by the user."


def test_hydrate_descriptions_leaves_unmatched_layers_blank():
    layer = Layer(name="Unknown Fill", thickness_in=Decimal(6))
    project = Project(info=ProjectInfo(), pits=[TrialPit(number="1", layers=[layer])])

    hydrate_descriptions(project, [])

    assert layer.description == ""


def test_hydrating_never_writes_back_to_the_template_store(tmp_path):
    path = tmp_path / "catalog.json"
    templates = [UnitTemplate(name="Topsoil", description="Template text.")]
    save_catalog(templates, path)

    layer = Layer(name="Topsoil", thickness_in=Decimal(12))
    project = Project(info=ProjectInfo(), pits=[TrialPit(number="1", layers=[layer])])
    loaded = load_catalog(path)
    hydrate_descriptions(project, loaded)
    layer.description = "User edited this specific drawing only."

    assert load_catalog(path) == templates
