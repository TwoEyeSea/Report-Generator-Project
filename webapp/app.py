"""Local web front-end over the tp_drawer library.

Upload the same .xlsx used with the CLI, get a scrollable preview of every
generated trial pit page, edit each unit's description live (the preview
re-renders after a short pause), and download the finished PDF. Thin wrapper
around tp_drawer.excel_io / tp_drawer.drawing / tp_drawer.catalog -- no
parsing or layout logic duplicated here.

PLAIN-ENGLISH OVERVIEW OF HOW A WEB APP LIKE THIS WORKS:
A web app is just a program that sits waiting for incoming HTTP requests
(the same kind your browser sends every time you visit a URL) and sends
back an HTTP response. Flask (the library imported below) is what
listens for those requests and hands each one to the right Python
function based on the URL that was requested. Each function below
decorated with `@app.route(...)` is one such handler -- e.g. when a
browser visits "/template", Flask calls the `template()` function and
sends whatever it returns back to the browser. Because HTTP requests
don't share any memory with each other (unlike function calls within one
Python program), anything that needs to survive between one request and
the next -- like "which project is this browser currently editing" --
has to be saved to disk and re-loaded on the next request; that's what
the job-directory/project.json mechanism below is for.
"""

import io
import json
import re
import time
import uuid
import zipfile
from dataclasses import fields as dataclass_fields
from pathlib import Path

import pymupdf
import pypdf
from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_file, send_from_directory, url_for

from tp_drawer.catalog import UnitTemplate, hydrate_descriptions, load_catalog, load_formation_catalog, load_foundation_catalog, save_catalog
from tp_drawer.config import Config
from tp_drawer.drawing import DescriptionBox, FieldBox, PitBoxes, compute_project_scale, render_hatch_swatch, render_location_plan_pdf, render_pit_pdf, resolve_field
from tp_drawer.excel_io import read_project, write_template
from tp_drawer.hatch_patterns import PATTERN_REGISTRY
from tp_drawer.models import Project, TrialPit, project_from_dict, project_to_dict
from tp_drawer.pdf_convert import convert_to_pdf
from tp_drawer.photo_gallery_io import generate_appendix_b, is_image_file
from tp_drawer.report_io import build_report_context, generate_report, render_docx_template
from tp_drawer.units import format_feet_inches, parse_feet_inches

APPENDIX_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "data"
APPENDIX_LETTERS = ("a", "b", "c", "d")
# Short, filename-friendly title for each appendix -- used to build names
# like "Appendix A Site Figures" for the export feature (see
# _export_basename/export below). Matches each appendix's own in-document
# subtitle except Appendix B, where "Photo Gallery" reads better in a
# filename than the document's own "Photographic Record" heading.
APPENDIX_TITLES = {
    "a": "Site Figures",
    "b": "Photo Gallery",
    "c": "Trial Pit Logs",
    "d": "Limitations",
}
# Appendices that also get a PDF copy alongside their .docx in the export
# zip -- B is left out since its captions/photos are the one appendix
# likely to still need hand review before it's considered final.
PDF_APPENDIX_LETTERS = {"a", "c", "d"}

OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# Characters that are illegal on Windows (or just awkward cross-platform)
# in a filename -- stripped from a project name before it's dropped into
# an exported file's download name (see _export_basename).
_FILENAME_UNSAFE_RE = re.compile(r'[<>:"/\\|?*]')


def _export_basename(project: Project) -> str:
    """The "<Project Name>" prefix every exported file/deliverable name
    starts with (see the export route below), e.g. "Dilbert Home" ->
    "Dilbert Home TP Logs.pdf". Falls back to a generic placeholder for
    a project whose name is blank or entirely made of unsafe characters,
    rather than producing a filename that starts with a bare extension."""
    cleaned = _FILENAME_UNSAFE_RE.sub("", project.info.project_name).strip()
    return cleaned or "Untitled Project"

# ADVANCED TECHNIQUE -- validating input with a regex, for security:
# _JOB_ID_RE only matches a string that's exactly 32 lowercase hex
# characters (0-9, a-f) -- exactly the shape of uuid.uuid4().hex below.
# Every route that takes a job_id from the URL (e.g. /edit/<job_id>)
# checks it against this pattern before using it to build a filesystem
# path. Without that check, a malicious visitor could try requesting
# something like "/outputs/../../../../etc/passwd" and trick the server
# into reading a file well outside the intended outputs/ folder -- a
# classic "path traversal" attack. Requiring the job_id to look like a
# genuine job id (which can never contain "/" or "..") closes that door
# before the value ever reaches a filesystem path. _OUTPUT_FILENAME_RE
# below does the same job for the filename half of that route.
_JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_OUTPUT_FILENAME_RE = re.compile(r"^(log\.pdf|pit_\d+\.png|pit_\d+_boxes\.json|pit_\d+_fields\.json)$")
_PREVIEW_DPI = 150

# Every click-to-edit FieldBox tp_drawer.drawing produces is tagged with a
# `box_id` (see FieldBox's own docstring); this registry is the other
# half of that contract -- for each box_id, which underlying field(s) a
# click on that box should let someone edit, what to label each one, and
# what kind of input control it needs ("text": a plain text field;
# "yesno": a Yes/No select, for pit.walls_stable; "depth": a feet-inches
# text field parsed/formatted via tp_drawer.units, for
# pit.groundwater_depth_in, where a blank value means "not encountered").
#
# Each field's key is "project:<attr>" (a shared ProjectInfo attribute --
# see tp_drawer.drawing.resolve_field -- editable either globally or, via
# TrialPit.field_overrides, for one pit only) or "pit:<attr>" (a
# TrialPit attribute with no shared/override split of its own -- editing
# it "globally" here instead means writing the same value onto every
# pit directly, see update_fields below).
FIELD_BOX_SPECS: dict[str, list[tuple[str, str, str]]] = {
    "general_notes": [
        ("project:equipment", "Equipment", "text"),
        ("project:equipment_provider", "Equipment Provider", "text"),
        ("project:ground_levels_note", "Ground Levels Note", "text"),
        ("project:site_work_completion_date", "Site Work Completion Date", "text"),
        ("project:file_ref", "File Reference", "text"),
        ("pit:groundwater_depth_in", "Groundwater Depth (blank = not encountered)", "depth"),
        ("pit:termination_reason", "Final Formation / Termination Reason", "text"),
        ("pit:extra_note", "Extra Note", "text"),
    ],
    "title_notes": [
        ("project:equipment", "Equipment", "text"),
        ("project:equipment_provider", "Equipment Provider", "text"),
        ("project:site_work_completion_date", "Site Work Completion Date", "text"),
        ("project:file_ref", "File Reference", "text"),
        ("pit:groundwater_depth_in", "Groundwater Depth (blank = not encountered)", "depth"),
        ("pit:walls_stable", "Pit Walls Stable", "yesno"),
    ],
    "project": [
        ("project:project_name", "Project Name", "text"),
        ("project:street_address", "Street Address", "text"),
        ("project:block_and_parcel", "Block and Parcel", "text"),
    ],
    "title": [
        ("pit:number", "Pit Number", "text"),
    ],
    "drawn_by": [
        ("project:drawn_by", "Drawn By", "text"),
    ],
    "scale": [
        ("project:scale_note", "Scale", "text"),
    ],
    "file": [
        ("project:file_ref", "File Reference", "text"),
    ],
}


# Every "pit:<attr>" key that appears anywhere in FIELD_BOX_SPECS above --
# validated against on the way into update_fields below so a malformed
# field_key can't setattr() an arbitrary, unintended TrialPit attribute.
_KNOWN_PIT_FIELDS = {key.split(":", 1)[1] for specs in FIELD_BOX_SPECS.values() for key, _, _ in specs if key.startswith("pit:")}


def _current_field_value(project: Project, pit: TrialPit, attr: str, *, is_project_field: bool) -> str:
    """The text a field's input box should be pre-filled with -- resolved
    through field_overrides for a "project:"-prefixed field (see
    resolve_field), or read straight off the pit for a "pit:"-prefixed
    one, with type-aware formatting for the two pit attributes that
    aren't already plain strings (groundwater_depth_in, walls_stable)."""
    if is_project_field:
        return resolve_field(project, pit, attr)
    value = getattr(pit, attr)
    if attr == "groundwater_depth_in":
        return format_feet_inches(value) if value is not None else ""
    if attr == "walls_stable":
        return "yes" if value else "no"
    return str(value)


def _convert_pit_field(attr: str, raw_value: str) -> object:
    """Parses one "pit:"-prefixed field's raw string from the click-to-edit
    popup back into the type TrialPit actually stores it as. Letting
    parse_feet_inches raise ValueError on unparseable text is deliberate --
    update_fields below catches it the same way it catches every other
    malformed-request error."""
    if attr == "groundwater_depth_in":
        text = raw_value.strip()
        return parse_feet_inches(text, context="click-to-edit groundwater depth") if text else None
    if attr == "walls_stable":
        return raw_value.strip().lower() in ("yes", "true", "1")
    return raw_value.strip()

# ADVANCED TECHNIQUE -- Flask's `app` object and decorators:
# `app` is the running web application itself; every `@app.route(...)`
# you'll see below is a *decorator* -- special syntax that wraps the
# function immediately under it and registers it with `app` as "the code
# to run when a request for this URL comes in". Decorators are a common
# Python pattern for attaching extra behavior to a function without
# changing the function's own body -- here, that extra behavior is
# "become reachable at this web address".
app = Flask(__name__)


def _job_dir(job_id: str) -> Path:
    """Every uploaded workbook gets its own folder under outputs/, named
    by a random job id, holding that one job's input file, generated
    PDF, preview images, and saved project.json -- this just builds the
    path to that folder."""
    return OUTPUTS_DIR / job_id


def _require_job_dir(job_id: str) -> Path:
    """Used at the top of every route that operates on an existing job:
    validates the job_id looks like a real one (see the _JOB_ID_RE
    comment above) and that its folder actually exists, calling Flask's
    abort(404) -- immediately stopping the request and sending back a
    standard "Not Found" page -- for either failure, rather than letting
    a bad or made-up job_id reach the rest of the route's logic."""
    if not _JOB_ID_RE.match(job_id):
        abort(404)
    job_dir = _job_dir(job_id)
    if not job_dir.is_dir():
        abort(404)
    return job_dir


def _load_project(job_dir: Path) -> Project:
    """Read this job's saved project.json back off disk into a real
    Project object -- the read half of the save/load round trip that
    lets a project survive between one HTTP request and the next (see
    the module docstring above)."""
    return project_from_dict(json.loads((job_dir / "project.json").read_text()))


def _save_project(job_dir: Path, project: Project) -> None:
    """The write half of the same round trip: serialize the current
    in-memory Project (via models.py's project_to_dict) and save it to
    this job's project.json, ready for _load_project to read back on the
    next request."""
    (job_dir / "project.json").write_text(json.dumps(project_to_dict(project)))


def _pit_pdf_path(job_dir: Path, pit_index: int) -> Path:
    """Where one pit's own single-page PDF lives within its job folder --
    an internal working file (never served to the browser directly, see
    _OUTPUT_FILENAME_RE above) that _rebuild_combined_pdf reads back to
    reassemble log.pdf without re-drawing anything."""
    return job_dir / f"pit_{pit_index}.pdf"


def _description_boxes_path(job_dir: Path, pit_index: int) -> Path:
    """Where one pit's click-to-edit coordinate map lives -- see
    _save_description_boxes below."""
    return job_dir / f"pit_{pit_index}_boxes.json"


def _save_description_boxes(job_dir: Path, pit_index: int, boxes: list[DescriptionBox], cfg: Config) -> None:
    """Persists one pit's DescriptionBox list (page-inches, y-up from the
    bottom -- see tp_drawer.drawing.DescriptionBox's own docstring) as
    fractions of the page's own width/height (0-1, y-down from the top --
    a browser positions an element over an <img> the same way, via CSS
    percentages), so the edit page's click-to-edit overlay can position a
    clickable region over the preview image without caring what pixel
    size that image actually got rasterized at."""
    page_w, page_h = cfg.page_size_in
    payload = [
        {
            "layer_index": box.layer_index,
            "x": box.x / page_w,
            "y": (page_h - box.y) / page_h,
            "width": box.width / page_w,
            "height": box.height / page_h,
        }
        for box in boxes
    ]
    _description_boxes_path(job_dir, pit_index).write_text(json.dumps(payload))


def _field_boxes_path(job_dir: Path, pit_index: int) -> Path:
    """Where one pit's field-editing coordinate map lives -- the
    "everything else" counterpart to _description_boxes_path above, for
    the NOTES/PROJECT/TITLE/DRAWN BY/SCALE/FILE boxes rather than
    per-layer descriptions."""
    return job_dir / f"pit_{pit_index}_fields.json"


def _save_field_boxes(job_dir: Path, pit_index: int, project: Project, pit: TrialPit, boxes: list[FieldBox], cfg: Config) -> None:
    """Persists one pit's FieldBox list the same way _save_description_boxes
    persists DescriptionBoxes (page-inches, y-up -> fractions of the
    page, y-down from the top), plus each box's own field metadata from
    FIELD_BOX_SPECS (label, input kind, and current value) so the edit
    page's popup can build its inputs without a separate request."""
    page_w, page_h = cfg.page_size_in
    payload = []
    for box in boxes:
        fields = [
            {
                "key": key,
                "label": label,
                "kind": kind,
                "value": _current_field_value(project, pit, key.split(":", 1)[1], is_project_field=key.startswith("project:")),
            }
            for key, label, kind in FIELD_BOX_SPECS.get(box.box_id, [])
        ]
        payload.append(
            {
                "box_id": box.box_id,
                "x": box.x / page_w,
                "y": (page_h - box.y) / page_h,
                "width": box.width / page_w,
                "height": box.height / page_h,
                "fields": fields,
            }
        )
    _field_boxes_path(job_dir, pit_index).write_text(json.dumps(payload))


def _render_and_rasterize_pit(job_dir: Path, project: Project, scale: float, templates: list[UnitTemplate], pit_index: int) -> None:
    """Regenerate exactly one pit's own PDF page, PNG preview, and
    click-to-edit coordinate map -- the only rendering work a single
    description edit actually needs, since editing one layer's text can
    only ever change that one pit's page (note: a long description can
    also push its *neighbors'* description blocks around via
    description_layout.py's reflow logic, which is exactly why this
    re-saves every layer's box on this pit, not just the edited one).

    render_pit_pdf (from tp_drawer.drawing) draws just this pit and
    returns where each layer's description block ended up; pymupdf then
    re-rasterizes that one-page PDF into a plain PNG image the same way
    the old whole-project version did, just for one page instead of every
    page (see render_pit_pdf's own docstring for why re-drawing every
    other pit here would be wasted work)."""
    pit = project.pits[pit_index]
    pdf_path = _pit_pdf_path(job_dir, pit_index)
    cfg = Config()
    boxes = render_pit_pdf(project, pit, cfg, scale, templates, pdf_path)
    _save_description_boxes(job_dir, pit_index, boxes.descriptions, cfg)
    _save_field_boxes(job_dir, pit_index, project, pit, boxes.fields, cfg)
    doc = pymupdf.open(pdf_path)
    doc[0].get_pixmap(dpi=_PREVIEW_DPI).save(job_dir / f"pit_{pit_index}.png")
    doc.close()


def _rebuild_combined_pdf(job_dir: Path, project: Project) -> None:
    """Reassemble the downloadable log.pdf out of every pit's own already-
    rendered single-page PDF (see _pit_pdf_path above). pypdf.PdfWriter
    here only ever copies each page's already-finished content across --
    it never re-draws anything -- so rebuilding the combined file after a
    single-pit edit stays cheap no matter how many pits the project has,
    unlike calling render_project again (which redraws every pit from
    scratch) would be."""
    writer = pypdf.PdfWriter()
    for i in range(len(project.pits)):
        reader = pypdf.PdfReader(_pit_pdf_path(job_dir, i))
        writer.add_page(reader.pages[0])
    with open(job_dir / "log.pdf", "wb") as f:
        writer.write(f)


def _render_and_rasterize_all(job_dir: Path, project: Project) -> None:
    """Full render of every pit -- used only right after a workbook is
    first uploaded, when every pit genuinely needs drawing at least once
    (there's no previous render anything could be reused from). Every
    later edit goes through _render_and_rasterize_pit instead, which only
    re-draws the one pit that actually changed."""
    templates = load_catalog()
    scale = compute_project_scale(project)
    for i in range(len(project.pits)):
        _render_and_rasterize_pit(job_dir, project, scale, templates, i)
    _rebuild_combined_pdf(job_dir, project)


@app.route("/")
def index():
    """The homepage -- just the upload form, defined entirely in
    webapp/templates/index.html. render_template renders that HTML file
    (Flask's templating engine can fill in dynamic values with `{{ ... }}`
    placeholders, though this particular page doesn't need any)."""
    return render_template("index.html")


@app.route("/template")
def template():
    """Lets a new user download a blank input workbook to fill in --
    generates it fresh into its own throwaway job folder (so it doesn't
    collide with any real job) and streams it back as a file download.
    uuid.uuid4().hex generates a random 32-character hex string -- see
    the _JOB_ID_RE comment above for why job folders are named this way
    rather than something predictable like an incrementing number."""
    job_dir = OUTPUTS_DIR / uuid.uuid4().hex
    job_dir.mkdir()
    path = job_dir / "template.xlsx"
    write_template(path)
    return send_file(path, as_attachment=True, download_name="trial_pit_input_template.xlsx")


@app.route("/generate", methods=["POST"])
def generate():
    """Handles the upload form's submission: this is the one route that
    turns an uploaded .xlsx into a brand new job. methods=["POST"] on the
    decorator restricts this route to POST requests (the kind a form
    submission sends, since it's *creating* something) rather than the
    plain GET requests every other route above/below responds to, which
    just fetch/view something without changing anything.

    The overall flow mirrors the CLI's `build` command (see cli.py's
    _cmd_build) almost exactly -- read the workbook, hydrate descriptions
    from the catalog, render -- with the extra step of saving everything
    into a fresh per-job folder so the browser can come back and edit it
    afterward."""
    upload = request.files.get("workbook")
    if upload is None or upload.filename == "":
        return render_template("index.html", error="Please choose an .xlsx file to upload."), 400

    job_id = uuid.uuid4().hex
    job_dir = _job_dir(job_id)
    job_dir.mkdir()

    workbook_path = job_dir / "input.xlsx"
    upload.save(workbook_path)

    try:
        project = read_project(workbook_path)
    except ValueError as exc:
        # A malformed workbook (e.g. an unparseable depth cell) is a
        # normal, expected possibility here -- send the user back to the
        # upload form with a helpful error message rather than crashing
        # the whole request with an unhandled exception.
        return render_template("index.html", error=str(exc)), 400

    hydrate_descriptions(project, load_catalog())

    _save_project(job_dir, project)
    _render_and_rasterize_all(job_dir, project)

    # redirect(...) sends the browser's next request to a different URL
    # -- here, on to the newly created job's edit page -- rather than
    # this route rendering that page's HTML itself. url_for("edit",
    # job_id=job_id) builds that URL from the `edit` route's own
    # definition below (e.g. "/edit/<job_id>") rather than hardcoding the
    # path as a raw string, so if that route's URL pattern ever changes,
    # this call site doesn't need to be updated to match.
    return redirect(url_for("edit", job_id=job_id))


@app.route("/edit/<job_id>")
def edit(job_id: str):
    """The editing page for one job: shows every pit's preview image
    alongside editable text boxes for each layer's description.
    `<job_id>` in the route path is a Flask URL variable -- whatever
    value appears in that position of the actual requested URL (e.g.
    "/edit/3f9a2b...") gets passed in as this function's `job_id`
    argument automatically.

    Builds a `pits` list of plain dicts (rather than passing the raw
    Project object straight to the template) so the HTML template only
    ever has to deal with simple, predictable data -- each pit's number,
    its index (used by edit_update below to know which pit a later edit
    belongs to), its layers, the URL of its preview image, and the URL of
    its click-to-edit coordinate map (see _save_description_boxes)."""
    job_dir = _require_job_dir(job_id)
    project = _load_project(job_dir)
    pits = [
        {
            "number": pit.number,
            "pit_index": i,
            "layers": [{"layer_index": j, "name": layer.name, "description": layer.description} for j, layer in enumerate(pit.layers)],
            "image_url": url_for("job_file", job_id=job_id, filename=f"pit_{i}.png"),
            "boxes_url": url_for("job_file", job_id=job_id, filename=f"pit_{i}_boxes.json"),
            "fields_url": url_for("job_file", job_id=job_id, filename=f"pit_{i}_fields.json"),
        }
        for i, pit in enumerate(project.pits)
    ]
    export_url = url_for("export", job_id=job_id)
    photo_dir = _photo_dir(job_dir)
    photos = sorted(p.name for p in photo_dir.iterdir() if p.is_file() and is_image_file(p)) if photo_dir.is_dir() else []
    return render_template("edit.html", job_id=job_id, pits=pits, export_url=export_url, photos=photos)


@app.route("/edit/<job_id>/update", methods=["POST"])
def edit_update(job_id: str):
    """Called by the edit page's JavaScript (via a background fetch, not
    a full page reload) every time the user pauses after editing a
    description box -- updates just that one layer's text, regenerates
    only that one pit's PDF page and preview image (see
    _render_and_rasterize_pit), and returns that one new preview image's
    URL for the page to swap in live.

    request.get_json(silent=True) parses the request body as JSON;
    silent=True means a malformed body returns None instead of raising an
    error, which the `or {}` right after turns into a safely-empty dict
    to look up from. The `try/except (KeyError, TypeError, ValueError)`
    then covers every way the expected fields could be missing or the
    wrong shape (KeyError: the key isn't present at all; TypeError: e.g.
    trying int() on something that isn't string/number-like; ValueError:
    e.g. int("not a number")) -- any of those means "the browser sent us
    something we don't understand", which gets reported back as a 400
    "Bad Request" JSON error rather than crashing the server."""
    job_dir = _require_job_dir(job_id)
    body = request.get_json(silent=True) or {}
    try:
        pit_index = int(body["pit_index"])
        layer_index = int(body["layer_index"])
        description = str(body["description"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Malformed update request."}), 400

    project = _load_project(job_dir)
    try:
        project.pits[pit_index].layers[layer_index].description = description
    except IndexError:
        # pit_index/layer_index parsed as valid integers, but don't
        # actually point at a real pit/layer in this project (e.g. the
        # browser's page is somehow out of sync with the saved project) --
        # reported the same way as a malformed request, just for a
        # different underlying reason.
        return jsonify({"error": "Unknown pit or layer index."}), 400

    _save_project(job_dir, project)
    # Only the edited pit's own page actually changed, so only it needs
    # re-rendering -- see _render_and_rasterize_pit's docstring. log.pdf
    # (the downloadable file) still needs to reflect the edit, but
    # _rebuild_combined_pdf does that by re-copying every pit's already-
    # rendered page rather than re-drawing any of them.
    templates = load_catalog()
    scale = compute_project_scale(project)
    _render_and_rasterize_pit(job_dir, project, scale, templates, pit_index)
    _rebuild_combined_pdf(job_dir, project)

    # Appending a `?v=<timestamp>` query string to the image URL is a
    # classic "cache-busting" trick: browsers aggressively cache images
    # by URL, so simply re-requesting "pit_0.png" after it's changed on
    # the server could show the browser's old cached copy instead of the
    # freshly re-rendered one. Since the timestamp is different every
    # time, the URL as a whole looks brand new to the browser's cache,
    # forcing it to fetch the actual latest image.
    cache_bust = int(time.time() * 1000)
    image_url = f"{url_for('job_file', job_id=job_id, filename=f'pit_{pit_index}.png')}?v={cache_bust}"
    # A long description can push its *neighbors'* description blocks
    # around too (see description_layout.py's reflow logic), so the
    # click-to-edit overlay needs every layer's box re-fetched after any
    # edit to this pit, not just the one that was just edited -- same
    # cache-busting reasoning as image_url above.
    boxes_url = f"{url_for('job_file', job_id=job_id, filename=f'pit_{pit_index}_boxes.json')}?v={cache_bust}"
    return jsonify({"pit_index": pit_index, "image_url": image_url, "boxes_url": boxes_url})


def _pit_urls(job_id: str, pit_index: int, cache_bust: int) -> dict:
    """The same cache-busted image/boxes/fields URL triple for one pit,
    shared by update_fields below -- a "global" field edit re-renders
    every pit at once, so this needs to be built once per affected pit
    rather than just the one edit_update above ever had to handle."""
    return {
        "pit_index": pit_index,
        "image_url": f"{url_for('job_file', job_id=job_id, filename=f'pit_{pit_index}.png')}?v={cache_bust}",
        "boxes_url": f"{url_for('job_file', job_id=job_id, filename=f'pit_{pit_index}_boxes.json')}?v={cache_bust}",
        "fields_url": f"{url_for('job_file', job_id=job_id, filename=f'pit_{pit_index}_fields.json')}?v={cache_bust}",
    }


@app.route("/edit/<job_id>/update_fields", methods=["POST"])
def edit_update_fields(job_id: str):
    """Called by the edit page's click-to-edit popup for every box other
    than a layer description (NOTES, PROJECT, TITLE, DRAWN BY, SCALE,
    FILE -- see FIELD_BOX_SPECS): applies one or more field edits to
    either just the clicked pit ("pit" scope) or every pit in the project
    ("global" scope), then re-renders whichever pit(s) that touched.

    request body: {"pit_index": int, "scope": "pit"|"global",
    "values": {field_key: str}}, where each field_key is one of
    FIELD_BOX_SPECS's own "project:<attr>"/"pit:<attr>" keys.

    A "project:" field writes straight to project.info on a "global" edit
    (clearing every pit's own override for it, so the new shared value
    isn't immediately masked again -- see resolve_field), or into just
    this pit's field_overrides on a "pit" edit. A "pit:" field writes
    directly onto every pit ("global") or just this one ("pit") -- there's
    no shared/override split for these, since they're TrialPit's own
    attributes rather than a ProjectInfo field being shadowed."""
    job_dir = _require_job_dir(job_id)
    body = request.get_json(silent=True) or {}
    try:
        pit_index = int(body["pit_index"])
        scope = str(body["scope"])
        values = dict(body["values"])
        if scope not in ("pit", "global"):
            raise ValueError("scope must be 'pit' or 'global'")
        if not values:
            raise ValueError("no field values submitted")

        project = _load_project(job_dir)
        pit = project.pits[pit_index]  # IndexError -> caught below

        for field_key, raw_value in values.items():
            prefix, attr = str(field_key).split(":", 1)
            raw_value = str(raw_value)
            if prefix == "project":
                if attr not in {f.name for f in dataclass_fields(type(project.info))}:
                    raise ValueError(f"unknown project field {attr!r}")
                value = raw_value.strip()
                if scope == "global":
                    setattr(project.info, attr, value)
                    for other_pit in project.pits:
                        other_pit.field_overrides.pop(attr, None)
                else:
                    pit.field_overrides[attr] = value
            elif prefix == "pit":
                if attr not in _KNOWN_PIT_FIELDS:
                    raise ValueError(f"unknown pit field {attr!r}")
                converted = _convert_pit_field(attr, raw_value)
                targets = project.pits if scope == "global" else [pit]
                for target in targets:
                    setattr(target, attr, converted)
            else:
                raise ValueError(f"malformed field key {field_key!r}")
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        return jsonify({"error": f"Malformed update request: {exc}"}), 400

    _save_project(job_dir, project)
    templates = load_catalog()
    scale = compute_project_scale(project)
    affected_indices = range(len(project.pits)) if scope == "global" else [pit_index]
    for i in affected_indices:
        _render_and_rasterize_pit(job_dir, project, scale, templates, i)
    _rebuild_combined_pdf(job_dir, project)

    cache_bust = int(time.time() * 1000)
    return jsonify({"pits": [_pit_urls(job_id, i, cache_bust) for i in affected_indices]})


def _photo_dir(job_dir: Path) -> Path:
    """Where a job's uploaded site photos live -- Appendix B's originals
    (photo_gallery_io.py resizes/compresses its own copies into a
    _processed/ subfolder of this same directory, alongside them)."""
    return job_dir / "photos"


@app.route("/edit/<job_id>/photos", methods=["POST"])
def upload_photos(job_id: str):
    """Saves whatever image files were submitted (the edit page's photo
    upload form allows selecting several at once) into this job's photo
    folder, for Appendix B to later match by filename -- see
    tp_drawer.photo_gallery_io. Re-uploading a file with the same name
    simply overwrites it (e.g. to replace a mis-named photo) rather than
    erroring or duplicating. Non-image files are silently skipped rather
    than rejecting the whole upload, since a folder picker can easily
    sweep up something like a .DS_Store or Thumbs.db alongside the
    real photos."""
    job_dir = _require_job_dir(job_id)
    photo_dir = _photo_dir(job_dir)
    photo_dir.mkdir(parents=True, exist_ok=True)
    for upload in request.files.getlist("photos"):
        name = Path(upload.filename or "").name  # strip any client-supplied path component
        if name and is_image_file(Path(name)):
            upload.save(photo_dir / name)
    return redirect(url_for("edit", job_id=job_id))


@app.route("/edit/<job_id>/photos/delete", methods=["POST"])
def delete_photo(job_id: str):
    """Removes one previously-uploaded photo by filename, from the edit
    page's list of currently-uploaded photos."""
    job_dir = _require_job_dir(job_id)
    name = Path(request.form.get("filename", "")).name
    if name:
        photo_path = _photo_dir(job_dir) / name
        if photo_path.is_file():
            photo_path.unlink()
    return redirect(url_for("edit", job_id=job_id))


def _write_appendices_to_zip(zf: zipfile.ZipFile, project: Project, job_dir: Path, base_context: dict) -> None:
    """Renders all 4 appendices fresh and writes each into `zf`, named
    "<Project Name> Appendix <Letter> <Title>.docx" (see APPENDIX_TITLES)
    -- shared by the "appendices" and "all" export combinations below, so
    the naming/rendering logic exists in exactly one place. A, C, and D
    (see PDF_APPENDIX_LETTERS) also get a PDF copy alongside their docx.

    A PDF conversion failure (LibreOffice missing, or the conversion
    itself failing) doesn't fail the whole export -- it's better to hand
    back every docx than none of it over one appendix's PDF not being
    possible right now."""
    base = _export_basename(project)
    for letter in APPENDIX_LETTERS:
        appendix_path = job_dir / f"appendix_{letter}.docx"
        template_path = APPENDIX_TEMPLATES_DIR / f"appendix_{letter}_template.docx"
        if letter == "b":
            generate_appendix_b(project, _photo_dir(job_dir), base_context, appendix_path)
        else:
            render_docx_template(template_path, base_context, appendix_path)
        display_name = f"{base} Appendix {letter.upper()} {APPENDIX_TITLES[letter]}"
        zf.write(appendix_path, f"{display_name}.docx")
        if letter in PDF_APPENDIX_LETTERS:
            try:
                pdf_path = convert_to_pdf(appendix_path)
            except Exception:
                continue
            zf.write(pdf_path, f"{display_name}.pdf")


_EXPORT_CHOICES = {"tp_logs", "report", "appendices", "site_plan", "all"}


@app.route("/export/<job_id>")
def export(job_id: str):
    """The edit page's single, consolidated download endpoint: `what`
    (from the export dropdown's <select name="what">) picks one of five
    combinations, each downloaded under a name that starts with the
    project's own name (see _export_basename) so a user working several
    projects can tell their downloads apart in a browser's downloads
    list. Every docx/PDF is rendered fresh from the job's current project
    data on every request (cheap enough not to bother caching), same
    reasoning the old separate report/report_bundle routes this replaces
    already used."""
    job_dir = _require_job_dir(job_id)
    project = _load_project(job_dir)
    what = request.args.get("what", "all")
    if what not in _EXPORT_CHOICES:
        abort(400)
    base = _export_basename(project)
    formation_templates = load_formation_catalog()
    foundation_options = load_foundation_catalog()

    if what == "tp_logs":
        return send_file(job_dir / "log.pdf", as_attachment=True, download_name=f"{base} TP Logs.pdf")

    if what == "report":
        report_path = job_dir / "report.docx"
        generate_report(project, report_path, formation_templates, foundation_options)
        return send_file(report_path, as_attachment=True, download_name=f"{base} Report.docx")

    if what == "site_plan":
        location_plan_path = job_dir / "trial_pit_location_plan.pdf"
        render_location_plan_pdf(project, Config(), location_plan_path)
        return send_file(location_plan_path, as_attachment=True, download_name=f"{base} Site Plan Title Block.pdf")

    base_context = build_report_context(project, formation_templates, foundation_options)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if what == "appendices":
            _write_appendices_to_zip(zf, project, job_dir, base_context)
            zip_name = f"{base} Appendices.zip"
        else:  # "all"
            zf.write(job_dir / "log.pdf", f"{base} TP Logs.pdf")
            report_path = job_dir / "report.docx"
            generate_report(project, report_path, formation_templates, foundation_options)
            zf.write(report_path, f"{base} Report.docx")
            _write_appendices_to_zip(zf, project, job_dir, base_context)
            location_plan_path = job_dir / "trial_pit_location_plan.pdf"
            render_location_plan_pdf(project, Config(), location_plan_path)
            zf.write(location_plan_path, f"{base} Site Plan Title Block.pdf")
            zip_name = f"{base} Full Export.zip"
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=zip_name, mimetype="application/zip")


@app.route("/outputs/<job_id>/<filename>")
def job_file(job_id: str, filename: str):
    """Serves one file out of a job's folder (a pit preview PNG, its
    click-to-edit coordinate map, or -- though the edit page's own export
    dropdown downloads it by a nicer name via /export/<job_id> instead --
    the raw combined log.pdf). Every image_url/boxes_url built above
    ultimately points here. Both URL parts are validated against the
    regexes defined near the top of this file before being used to build
    a filesystem path -- see the _JOB_ID_RE comment above for why that
    matters."""
    if not _JOB_ID_RE.match(job_id) or not _OUTPUT_FILENAME_RE.match(filename):
        abort(404)
    job_dir = _job_dir(job_id)
    if not job_dir.is_dir():
        abort(404)
    return send_from_directory(job_dir, filename)


def _pattern_registry_context() -> dict:
    """Shrinks hatch_patterns.PATTERN_REGISTRY down to just the bits the
    catalog editor's HTML/JavaScript actually needs (id, display name,
    default angle/size) -- the registry's `generate` function reference
    itself is Python-only and has no meaning to send to a browser, so
    it's deliberately left out here."""
    return {
        pattern_id: {
            "display_name": pattern.display_name,
            "default_angle": pattern.default_angle,
            "default_size": pattern.default_size,
        }
        for pattern_id, pattern in PATTERN_REGISTRY.items()
    }


@app.route("/catalog")
def catalog_page():
    """The unit-template management page: lists every saved template
    (name, description, hatch styling) with forms to add, edit, and
    delete entries -- this route only *displays* that page; the actual
    add/update/delete actions are separate routes below, each one a
    plain HTML form submission (no live JavaScript editing here, unlike
    the trial-pit edit page above)."""
    templates = load_catalog()
    return render_template("catalog.html", templates=templates, pattern_registry=_pattern_registry_context())


_IS_NATIVE_FORM_VALUES = {"native": True, "made": False}


def _unit_template_from_form(name: str, description: str) -> UnitTemplate:
    """Shared by catalog_add and catalog_update below: reads the hatch
    styling fields (pattern/angle/size/colors) and the native/made radio
    choice out of the submitted form and builds a UnitTemplate from them,
    so both routes construct a template the exact same way rather than
    duplicating this field-by-field extraction twice."""
    background_color = "none" if request.form.get("background_nofill") else request.form.get("background_color", "none")
    return UnitTemplate(
        name=name,
        description=description,
        hatch_pattern=request.form.get("hatch_pattern", "none"),
        hatch_angle=request.form.get("hatch_angle", type=float) or 0.0,
        hatch_size=request.form.get("hatch_size", type=float) or 1.0,
        background_color=background_color,
        line_color=request.form.get("line_color", "black"),
        # Neither radio checked (e.g. a template saved before this field
        # existed, left alone) -> None, same "not set yet" state load_catalog
        # already gives an entry with no is_native key at all.
        is_native=_IS_NATIVE_FORM_VALUES.get(request.form.get("is_native", "")),
    )


@app.route("/catalog/add", methods=["POST"])
def catalog_add():
    """Adds one brand new template to the catalog from the "add" form at
    the bottom of the catalog page. A blank name is silently ignored
    (rather than shown as an error) -- the template-less UnitTemplate
    dataclass default `name: str` (no default value) means this route
    can't accidentally create a nameless entry either way, but checking
    up front avoids even attempting to."""
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if name:
        templates = load_catalog()
        templates.append(_unit_template_from_form(name, description))
        save_catalog(templates)
    return redirect(url_for("catalog_page"))


@app.route("/catalog/update", methods=["POST"])
def catalog_update():
    """Overwrites one existing catalog entry, identified by its position
    (`index`) in the list -- the catalog page's "Save" button on each row
    submits the whole catalog list's index alongside that row's edited
    fields. `0 <= index < len(templates)` guards against an index that's
    somehow out of range (e.g. the catalog changed in another browser tab
    since this page was loaded) -- silently doing nothing rather than
    crashing on a list index that no longer exists."""
    index = request.form.get("index", type=int)
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    templates = load_catalog()
    if index is not None and 0 <= index < len(templates) and name:
        templates[index] = _unit_template_from_form(name, description)
        save_catalog(templates)
    return redirect(url_for("catalog_page"))


@app.route("/catalog/swatch.png")
def catalog_swatch():
    """Renders one live thumbnail image for the catalog editor -- as the
    user tweaks a pattern/angle/size/color in the add or edit form, the
    page's JavaScript re-requests this URL with the current field values
    as query-string parameters (`request.args`, as opposed to the
    `request.form` used by the POST routes above, since this is a plain
    GET request driven by a changing `<img src="...">`), and gets back a
    fresh PNG reflecting exactly what would be drawn on the real log."""
    pattern_id = request.args.get("pattern", "none")
    angle = request.args.get("angle", type=float) or 0.0
    size = request.args.get("size", type=float) or 1.0
    background_color = request.args.get("bg", "none")
    line_color = request.args.get("line", "black")
    if pattern_id not in PATTERN_REGISTRY:
        abort(404)
    png_bytes = render_hatch_swatch(pattern_id, angle, size, background_color, line_color)
    return Response(png_bytes, mimetype="image/png")


@app.route("/catalog/delete", methods=["POST"])
def catalog_delete():
    """Removes one catalog entry by its list position -- `del
    templates[index]` removes that one item from the in-memory list
    (leaving every other entry's position unaffected, since the list
    resizes to close the gap), and save_catalog then writes the shortened
    list back out to disk."""
    index = request.form.get("index", type=int)
    templates = load_catalog()
    if index is not None and 0 <= index < len(templates):
        del templates[index]
        save_catalog(templates)
    return redirect(url_for("catalog_page"))


def main(host: str = "127.0.0.1", port: int = 5000) -> None:
    """Starts the actual web server, listening on the given host/port --
    called by both `python -m webapp.app` (via the __main__ guard below)
    and `tp_drawer serve` (see cli.py's _cmd_serve, which imports and
    calls this same function). debug=False disables Flask's development
    auto-reloader and interactive in-browser debugger/traceback pages --
    appropriate for a tool a non-programmer will actually run, where a
    raw Python traceback or an unintentionally-exposed code-execution
    debug console would be far more confusing/risky than helpful."""
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
