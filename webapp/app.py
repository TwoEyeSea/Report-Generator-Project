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

import json
import re
import time
import uuid
from pathlib import Path

import pymupdf
import pypdf
from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_file, send_from_directory, url_for

from tp_drawer.catalog import UnitTemplate, hydrate_descriptions, load_catalog, save_catalog
from tp_drawer.config import Config
from tp_drawer.drawing import compute_project_scale, render_hatch_swatch, render_pit_pdf
from tp_drawer.excel_io import read_project, write_template
from tp_drawer.hatch_patterns import PATTERN_REGISTRY
from tp_drawer.models import Project, project_from_dict, project_to_dict

OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

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
_OUTPUT_FILENAME_RE = re.compile(r"^(log\.pdf|pit_\d+\.png)$")
_PREVIEW_DPI = 150

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


def _render_and_rasterize_pit(job_dir: Path, project: Project, scale: float, templates: list[UnitTemplate], pit_index: int) -> None:
    """Regenerate exactly one pit's own PDF page and PNG preview -- the
    only rendering work a single description edit actually needs, since
    editing one layer's text can only ever change that one pit's page.

    render_pit_pdf (from tp_drawer.drawing) draws just this pit; pymupdf
    then re-rasterizes that one-page PDF into a plain PNG image the same
    way the old whole-project version did, just for one page instead of
    every page (see render_pit_pdf's own docstring for why re-drawing
    every other pit here would be wasted work)."""
    pit = project.pits[pit_index]
    pdf_path = _pit_pdf_path(job_dir, pit_index)
    render_pit_pdf(project, pit, Config(), scale, templates, pdf_path)
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
    belongs to), its layers, and the URL of its preview image."""
    job_dir = _require_job_dir(job_id)
    project = _load_project(job_dir)
    pits = [
        {
            "number": pit.number,
            "pit_index": i,
            "layers": [{"layer_index": j, "name": layer.name, "description": layer.description} for j, layer in enumerate(pit.layers)],
            "image_url": url_for("job_file", job_id=job_id, filename=f"pit_{i}.png"),
        }
        for i, pit in enumerate(project.pits)
    ]
    pdf_url = url_for("job_file", job_id=job_id, filename="log.pdf")
    return render_template("edit.html", job_id=job_id, pits=pits, pdf_url=pdf_url)


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
    return jsonify({"pit_index": pit_index, "image_url": image_url})


@app.route("/outputs/<job_id>/<filename>")
def job_file(job_id: str, filename: str):
    """Serves one file out of a job's folder (a preview PNG or the final
    PDF) -- every image_url and pdf_url built above ultimately points
    here. Both URL parts are validated against the regexes defined near
    the top of this file before being used to build a filesystem path --
    see the _JOB_ID_RE comment above for why that matters."""
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


def _unit_template_from_form(name: str, description: str) -> UnitTemplate:
    """Shared by catalog_add and catalog_update below: reads the hatch
    styling fields (pattern/angle/size/colors) out of the submitted form
    and builds a UnitTemplate from them, so both routes construct a
    template the exact same way rather than duplicating this field-by-
    field extraction twice."""
    background_color = "none" if request.form.get("background_nofill") else request.form.get("background_color", "none")
    return UnitTemplate(
        name=name,
        description=description,
        hatch_pattern=request.form.get("hatch_pattern", "none"),
        hatch_angle=request.form.get("hatch_angle", type=float) or 0.0,
        hatch_size=request.form.get("hatch_size", type=float) or 1.0,
        background_color=background_color,
        line_color=request.form.get("line_color", "black"),
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
