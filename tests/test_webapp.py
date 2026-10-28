import io
import json
import shutil

import pytest

from webapp.app import OUTPUTS_DIR, app

from .conftest import DEFAULT_HEADER, make_workbook


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    # Snapshot which job folders already exist *before* the test runs, so
    # teardown only removes ones this test itself created -- OUTPUTS_DIR
    # is the same outputs/ folder a real, locally-running instance of the
    # app uses for actual jobs. Wiping every child unconditionally (the
    # previous behavior here) deletes real user data the instant anyone
    # runs the test suite against a checkout that also has the webapp
    # running locally with real jobs in it.
    pre_existing = set(OUTPUTS_DIR.iterdir()) if OUTPUTS_DIR.exists() else set()
    with app.test_client() as c:
        yield c
    if OUTPUTS_DIR.exists():
        for child in OUTPUTS_DIR.iterdir():
            if child not in pre_existing:
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
    assert "boxes_url" in body

    project_data = json.loads((OUTPUTS_DIR / job_id / "project.json").read_text())
    assert project_data["pits"][0]["layers"][0]["description"] == "A freshly edited description."


def test_edit_page_serves_a_click_to_edit_box_per_layer(client, tmp_path):
    # _valid_workbook_bytes gives pit 1 two layers (Topsoil, Peat) -- see
    # the click-to-edit overlay's coordinate map for each.
    job_id = _generate(client, tmp_path)

    edit_page = client.get(f"/edit/{job_id}")
    assert b"pit_0_boxes.json" in edit_page.data

    response = client.get(f"/outputs/{job_id}/pit_0_boxes.json")
    assert response.status_code == 200
    assert response.content_type == "application/json"
    boxes = response.get_json()
    assert [box["layer_index"] for box in boxes] == [0, 1]
    for box in boxes:
        # Fractions of the page's own width/height (0-1), not pixels --
        # see webapp.app._save_description_boxes.
        assert 0 <= box["x"] <= 1
        assert 0 <= box["y"] <= 1
        assert 0 < box["width"] <= 1
        assert 0 < box["height"] <= 1


def test_edit_update_refreshes_box_coordinates_for_every_layer(client, tmp_path):
    # A long enough description can push a *later* layer's description
    # block down the page too (description_layout.py's reflow) -- editing
    # one layer must re-save every layer's box on that pit, not just the
    # edited one.
    job_id = _generate(client, tmp_path)
    before = client.get(f"/outputs/{job_id}/pit_0_boxes.json").get_json()

    response = client.post(
        f"/edit/{job_id}/update",
        json={"pit_index": 0, "layer_index": 0, "description": "A much, much longer description. " * 12},
    )
    assert response.status_code == 200

    after = client.get(f"/outputs/{job_id}/pit_0_boxes.json").get_json()
    assert [box["layer_index"] for box in after] == [box["layer_index"] for box in before]
    assert after != before  # at least the edited layer's own box grew taller


def test_edit_page_serves_a_field_box_per_labelled_box(client, tmp_path):
    job_id = _generate(client, tmp_path)

    edit_page = client.get(f"/edit/{job_id}")
    assert b"pit_0_fields.json" in edit_page.data

    response = client.get(f"/outputs/{job_id}/pit_0_fields.json")
    assert response.status_code == 200
    boxes = response.get_json()
    assert {box["box_id"] for box in boxes} == {"general_notes", "title_notes", "project", "title", "drawn_by", "scale", "file"}
    for box in boxes:
        assert 0 <= box["x"] <= 1
        assert 0 <= box["y"] <= 1
        assert 0 < box["width"] <= 1
        assert 0 < box["height"] <= 1
        assert box["fields"]  # every box has at least one editable field
        for field in box["fields"]:
            assert set(field) == {"key", "label", "kind", "value"}


def test_update_fields_pit_scope_only_changes_that_pit(client, tmp_path):
    job_id = _generate(client, tmp_path)

    response = client.post(
        f"/edit/{job_id}/update_fields",
        json={"pit_index": 0, "scope": "pit", "values": {"project:drawn_by": "ABC"}},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert [p["pit_index"] for p in body["pits"]] == [0]

    project_data = json.loads((OUTPUTS_DIR / job_id / "project.json").read_text())
    assert project_data["pits"][0]["field_overrides"]["drawn_by"] == "ABC"
    assert project_data["info"]["drawn_by"] != "ABC"

    fields_0 = client.get(f"/outputs/{job_id}/pit_0_fields.json").get_json()
    fields_1 = client.get(f"/outputs/{job_id}/pit_1_fields.json").get_json()
    drawn_by_0 = next(f["value"] for box in fields_0 if box["box_id"] == "drawn_by" for f in box["fields"])
    drawn_by_1 = next(f["value"] for box in fields_1 if box["box_id"] == "drawn_by" for f in box["fields"])
    assert drawn_by_0 == "ABC"
    assert drawn_by_1 != "ABC"


def test_update_fields_global_scope_changes_every_pit_and_clears_overrides(client, tmp_path):
    job_id = _generate(client, tmp_path)

    client.post(
        f"/edit/{job_id}/update_fields",
        json={"pit_index": 0, "scope": "pit", "values": {"project:drawn_by": "ABC"}},
    )
    response = client.post(
        f"/edit/{job_id}/update_fields",
        json={"pit_index": 0, "scope": "global", "values": {"project:drawn_by": "XYZ"}},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert {p["pit_index"] for p in body["pits"]} == {0, 1}

    project_data = json.loads((OUTPUTS_DIR / job_id / "project.json").read_text())
    assert project_data["info"]["drawn_by"] == "XYZ"
    assert "drawn_by" not in project_data["pits"][0]["field_overrides"]


def test_update_fields_pit_only_field_global_scope_applies_to_every_pit(client, tmp_path):
    job_id = _generate(client, tmp_path)

    response = client.post(
        f"/edit/{job_id}/update_fields",
        json={"pit_index": 0, "scope": "global", "values": {"pit:walls_stable": "no"}},
    )
    assert response.status_code == 200

    project_data = json.loads((OUTPUTS_DIR / job_id / "project.json").read_text())
    assert project_data["pits"][0]["walls_stable"] is False
    assert project_data["pits"][1]["walls_stable"] is False


def test_update_fields_depth_field_round_trips_and_blank_clears_it(client, tmp_path):
    job_id = _generate(client, tmp_path)

    response = client.post(
        f"/edit/{job_id}/update_fields",
        json={"pit_index": 0, "scope": "pit", "values": {"pit:groundwater_depth_in": "5'-0\""}},
    )
    assert response.status_code == 200
    project_data = json.loads((OUTPUTS_DIR / job_id / "project.json").read_text())
    assert project_data["pits"][0]["groundwater_depth_in"] == "60"

    client.post(
        f"/edit/{job_id}/update_fields",
        json={"pit_index": 0, "scope": "pit", "values": {"pit:groundwater_depth_in": ""}},
    )
    project_data = json.loads((OUTPUTS_DIR / job_id / "project.json").read_text())
    assert project_data["pits"][0]["groundwater_depth_in"] is None


def test_update_fields_rejects_unknown_field_key(client, tmp_path):
    job_id = _generate(client, tmp_path)

    response = client.post(
        f"/edit/{job_id}/update_fields",
        json={"pit_index": 0, "scope": "pit", "values": {"project:not_a_real_field": "x"}},
    )
    assert response.status_code == 400


def test_update_fields_rejects_bad_scope(client, tmp_path):
    job_id = _generate(client, tmp_path)

    response = client.post(
        f"/edit/{job_id}/update_fields",
        json={"pit_index": 0, "scope": "everywhere", "values": {"project:drawn_by": "ABC"}},
    )
    assert response.status_code == 400


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
