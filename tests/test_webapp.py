import io
import json
import shutil

import pytest

from webapp.app import OUTPUTS_DIR, app

from .conftest import DEFAULT_HEADER, make_workbook


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c
    # Clean up any job folders created during the test.
    if OUTPUTS_DIR.exists():
        for child in OUTPUTS_DIR.iterdir():
            shutil.rmtree(child, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated_catalog(tmp_path, monkeypatch):
    """Point the catalog at a throwaway file so webapp tests never touch data/unit_catalog.json."""
    from tp_drawer import catalog

    path = tmp_path / "catalog.json"
    monkeypatch.setattr(catalog, "DEFAULT_CATALOG_PATH", path)
    monkeypatch.setattr("webapp.app.load_catalog", lambda: catalog.load_catalog(path))
    monkeypatch.setattr("webapp.app.save_catalog", lambda templates: catalog.save_catalog(templates, path))
    return path


def _valid_workbook_bytes(tmp_path) -> bytes:
    path = tmp_path / "input.xlsx"
    make_workbook(
        path,
        DEFAULT_HEADER,
        pit_numbers=[1, 2],
        layers=[
            ("Topsoil\n(Layer thickness)", ["3'-5\"", "3'-10\""]),
            ("Peat\n(Layer thickness)", ["1'-10\"", "1'-3\""]),
        ],
        groundwater=["7'-2\"", "4'-11\""],
    )
    return path.read_bytes()


def _generate(client, tmp_path):
    data = {"workbook": (io.BytesIO(_valid_workbook_bytes(tmp_path)), "input.xlsx")}
    response = client.post("/generate", data=data, content_type="multipart/form-data")
    assert response.status_code == 302
    job_id = response.headers["Location"].rstrip("/").split("/")[-1]
    return job_id


def test_index_shows_upload_form(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Generate" in response.data
    assert b"workbook" in response.data


def test_generate_valid_workbook_redirects_to_edit_with_previews(client, tmp_path):
    data = {
        "workbook": (io.BytesIO(_valid_workbook_bytes(tmp_path)), "input.xlsx"),
    }
    response = client.post("/generate", data=data, content_type="multipart/form-data")
    assert response.status_code == 302
    assert "/edit/" in response.headers["Location"]

    result = client.get(response.headers["Location"])
    assert result.status_code == 200
    assert result.data.count(b"<img") == 2
    assert b"TRIAL PIT NO. 1" in result.data
    assert b"TRIAL PIT NO. 2" in result.data
    assert b"<textarea" in result.data


def test_generate_malformed_workbook_shows_error(client, tmp_path):
    path = tmp_path / "bad.xlsx"
    make_workbook(
        path,
        DEFAULT_HEADER,
        pit_numbers=[1],
        layers=[("Topsoil\n(Layer thickness)", ["not-a-dimension"])],
        groundwater=["7'-2\""],
    )
    data = {"workbook": (io.BytesIO(path.read_bytes()), "bad.xlsx")}
    response = client.post("/generate", data=data, content_type="multipart/form-data")
    assert response.status_code == 400
    assert b"Cannot parse feet-inches value" in response.data


def test_generate_without_file_shows_error(client):
    response = client.post("/generate", data={}, content_type="multipart/form-data")
    assert response.status_code == 400


def test_generate_hydrates_descriptions_from_catalog(client, tmp_path, isolated_catalog):
    from tp_drawer.catalog import UnitTemplate, save_catalog

    save_catalog([UnitTemplate(name="Topsoil", description="Dark brown organic silt.")], isolated_catalog)

    job_id = _generate(client, tmp_path)
    result = client.get(f"/edit/{job_id}")

    assert b"Dark brown organic silt." in result.data


def test_edit_update_changes_description_and_returns_new_previews(client, tmp_path):
    job_id = _generate(client, tmp_path)

    response = client.post(
        f"/edit/{job_id}/update",
        json={"pit_index": 0, "layer_index": 0, "description": "A freshly edited description."},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["pit_index"] == 0
    assert "image_url" in body

    project_data = json.loads((OUTPUTS_DIR / job_id / "project.json").read_text())
    assert project_data["pits"][0]["layers"][0]["description"] == "A freshly edited description."


def test_edit_update_never_touches_the_catalog_store(client, tmp_path, isolated_catalog):
    from tp_drawer.catalog import UnitTemplate, load_catalog, save_catalog

    save_catalog([UnitTemplate(name="Topsoil", description="Template text.")], isolated_catalog)
    job_id = _generate(client, tmp_path)

    client.post(
        f"/edit/{job_id}/update",
        json={"pit_index": 0, "layer_index": 0, "description": "Edited only in this drawing."},
    )

    assert load_catalog(isolated_catalog)[0].description == "Template text."


def test_edit_update_rejects_out_of_range_index(client, tmp_path):
    job_id = _generate(client, tmp_path)

    response = client.post(f"/edit/{job_id}/update", json={"pit_index": 99, "layer_index": 0, "description": "x"})

    assert response.status_code == 400


def test_edit_rejects_invalid_job_id(client):
    response = client.get("/edit/not-a-uuid")
    assert response.status_code == 404


def test_job_file_rejects_path_traversal(client):
    response = client.get("/outputs/" + "a" * 32 + "/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code == 404


def test_job_file_rejects_invalid_job_id(client):
    response = client.get("/outputs/not-a-uuid/log.pdf")
    assert response.status_code == 404


def test_template_download(client):
    response = client.get("/template")
    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith("attachment")


def test_catalog_page_lists_templates(client, isolated_catalog):
    from tp_drawer.catalog import UnitTemplate, save_catalog

    save_catalog([UnitTemplate(name="Peat", description="Fibrous, saturated.")], isolated_catalog)

    response = client.get("/catalog")

    assert response.status_code == 200
    assert b"Peat" in response.data
    assert b"Fibrous, saturated." in response.data


def test_catalog_add_appends_a_template(client, isolated_catalog):
    from tp_drawer.catalog import load_catalog

    response = client.post("/catalog/add", data={"name": "Gravel", "description": "Loose, coarse."})

    assert response.status_code == 302
    templates = load_catalog(isolated_catalog)
    assert templates[-1].name == "Gravel"
    assert templates[-1].description == "Loose, coarse."


def test_catalog_update_edits_in_place(client, isolated_catalog):
    from tp_drawer.catalog import UnitTemplate, load_catalog, save_catalog

    save_catalog([UnitTemplate(name="Peat", description="Old text.")], isolated_catalog)

    client.post("/catalog/update", data={"index": "0", "name": "Peat", "description": "New text."})

    assert load_catalog(isolated_catalog)[0].description == "New text."


def test_catalog_delete_removes_the_template(client, isolated_catalog):
    from tp_drawer.catalog import UnitTemplate, load_catalog, save_catalog

    save_catalog([UnitTemplate(name="Peat", description="x")], isolated_catalog)

    client.post("/catalog/delete", data={"index": "0"})

    assert load_catalog(isolated_catalog) == []


def test_catalog_add_persists_hatch_fields(client, isolated_catalog):
    from tp_drawer.catalog import load_catalog

    response = client.post(
        "/catalog/add",
        data={
            "name": "Clay",
            "description": "Firm brown clay.",
            "hatch_pattern": "dashes",
            "hatch_angle": "45",
            "hatch_size": "1.5",
            "background_color": "#cbb994",
            "line_color": "#3a2f1c",
        },
    )

    assert response.status_code == 302
    template = load_catalog(isolated_catalog)[-1]
    assert template.hatch_pattern == "dashes"
    assert template.hatch_angle == 45.0
    assert template.hatch_size == 1.5
    assert template.background_color == "#cbb994"
    assert template.line_color == "#3a2f1c"


def test_catalog_add_no_fill_checkbox_overrides_background_color(client, isolated_catalog):
    from tp_drawer.catalog import load_catalog

    client.post(
        "/catalog/add",
        data={
            "name": "Gravel",
            "description": "",
            "hatch_pattern": "gravel",
            "background_color": "#ffffff",
            "background_nofill": "on",
        },
    )

    assert load_catalog(isolated_catalog)[-1].background_color == "none"


def test_catalog_update_edits_hatch_fields_in_place(client, isolated_catalog):
    from tp_drawer.catalog import UnitTemplate, load_catalog, save_catalog

    save_catalog([UnitTemplate(name="Peat", description="x", hatch_pattern="none")], isolated_catalog)

    client.post(
        "/catalog/update",
        data={
            "index": "0",
            "name": "Peat",
            "description": "x",
            "hatch_pattern": "organic",
            "hatch_angle": "10",
            "hatch_size": "0.7",
            "background_color": "#556b2f",
            "line_color": "#101010",
        },
    )

    template = load_catalog(isolated_catalog)[0]
    assert template.hatch_pattern == "organic"
    assert template.hatch_angle == 10.0
    assert template.hatch_size == 0.7


def test_catalog_swatch_returns_a_png_image(client):
    response = client.get("/catalog/swatch.png?pattern=dashes&angle=30&size=1&bg=%23cbb994&line=%23000000")

    assert response.status_code == 200
    assert response.content_type == "image/png"
    assert len(response.data) > 0


def test_catalog_swatch_rejects_unknown_pattern(client):
    response = client.get("/catalog/swatch.png?pattern=not-a-real-pattern")

    assert response.status_code == 404
