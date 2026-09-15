"""Persistent databases of report boilerplate: subsurface unit templates
(name + description + hatch styling), named formation commentary, and
named foundation write-ups.

Templates are the source of truth for a unit's boilerplate description text.
`hydrate_descriptions` copies a matching template's text into a project's
Layer objects -- from that point on, editing a project's descriptions never
touches the template store. FormationTemplate and FoundationOption below
follow the exact same load/save/find-by-name shape, feeding
tp_drawer.report_io instead of the trial pit log drawing.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tp_drawer.models import Project

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "unit_catalog.json"


@dataclass
class UnitTemplate:
    """The "master record" for one named soil unit (e.g. "CLAY"): its
    standard description text plus how it should be drawn (hatch_pattern
    and friends -- see hatch_patterns.py for what those values mean).
    Stored centrally in data/unit_catalog.json via load_catalog/save_catalog
    below, so every project that uses a unit called "CLAY" looks the same."""

    name: str
    description: str = ""
    hatch_pattern: str = "none"
    hatch_angle: float = 0.0
    hatch_size: float = 1.0
    background_color: str = "none"
    line_color: str = "black"
    # True = native ground, False = made ground (fill), None = not set yet.
    # None is a deliberate third state, not just "defaults to made/native"
    # -- see hydrate_descriptions and report_io.py's _build_strata, which
    # render it as an explicit placeholder rather than guessing.
    is_native: bool | None = None


def load_catalog(path: str | Path = DEFAULT_CATALOG_PATH) -> list[UnitTemplate]:
    """Read the catalog JSON file off disk and turn it into a list of
    UnitTemplate objects. Missing file -> empty catalog (e.g. a brand new
    install with nothing saved yet) rather than an error."""
    path = Path(path)
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    # `UnitTemplate(**entry)` unpacks a dict like {"name": "CLAY",
    # "description": "..."} into keyword arguments -- equivalent to
    # writing UnitTemplate(name="CLAY", description="...") by hand, but
    # works for whatever keys happen to be in the dict without listing
    # them one by one. This is the mirror image of asdict(t) below, which
    # goes the other way (object -> dict).
    return [UnitTemplate(**entry) for entry in raw]


def save_catalog(templates: list[UnitTemplate], path: str | Path = DEFAULT_CATALOG_PATH) -> None:
    """Write the whole catalog back out to disk as JSON, overwriting
    whatever was there before -- this is a "save everything" operation,
    not an append."""
    path = Path(path)
    # exist_ok=True means "don't raise an error if data/ already exists" --
    # without it, mkdir would fail every time except the very first save.
    path.parent.mkdir(parents=True, exist_ok=True)
    # asdict(t) converts a dataclass instance back into a plain dict (the
    # reverse of UnitTemplate(**entry) above), which json.dumps can then
    # turn into text. indent=2 just makes the saved file human-readable if
    # someone opens it in a text editor, rather than one long unbroken line.
    path.write_text(json.dumps([asdict(t) for t in templates], indent=2))


def _find_by_name(name: str, items: list):
    """Shared lookup behind find_template/find_formation/find_foundation_option:
    match by name, ignoring case and stray leading/trailing spaces (so
    "Clay", " CLAY ", and "clay" all match the same entry -- forgiving of
    small inconsistencies in how a name was typed on the input
    spreadsheet). Returns None, rather than raising an error, when nothing
    matches -- callers are expected to handle "no entry for this name" as
    a normal, non-exceptional case."""
    key = name.strip().lower()
    for item in items:
        if item.name.strip().lower() == key:
            return item
    return None


def find_template(name: str, templates: list[UnitTemplate]) -> UnitTemplate | None:
    """Look up a unit template by name -- see _find_by_name."""
    return _find_by_name(name, templates)


def hydrate_descriptions(project: Project, templates: list[UnitTemplate]) -> None:
    """Copy each layer's matching template's description and native/made
    status in, for whichever of those two the layer doesn't already carry
    (independently -- a layer with a hand-typed description but no
    is_native yet still gets is_native filled in). Never writes back to
    `templates` -- a one-way copy."""
    for pit in project.pits:
        for layer in pit.layers:
            template = find_template(layer.name, templates)
            if template is None:
                continue
            if not layer.description:
                # This layer already has its own description (e.g. typed
                # in by the user, or hydrated on a previous run) -- leave
                # it alone rather than clobbering it with the generic
                # catalog text.
                layer.description = template.description
            if layer.is_native is None:
                layer.is_native = template.is_native


DEFAULT_FORMATION_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "formation_catalog.json"


@dataclass
class FormationTemplate:
    """The "master record" for one named bedrock/competent formation (e.g.
    "Ironshore Formation Limestone"): the boilerplate geological commentary
    the report's DISCUSSION section uses for it. `commentary` is a
    str.format() template with one placeholder, `{depth}`, filled in with
    the depth at which the formation was actually encountered on a given
    project (see report_io.py) -- everything else about a formation's
    geological setting is the same from project to project, which is
    exactly what makes it worth storing once here rather than retyping it
    into every report. New formations start with no commentary on file;
    report_io.py falls back to a placeholder note in that case rather
    than failing, the same way an unrecognised soil unit above just gets
    no auto-filled description."""

    name: str
    commentary: str = ""


def load_formation_catalog(path: str | Path = DEFAULT_FORMATION_CATALOG_PATH) -> list[FormationTemplate]:
    """Read the formation catalog JSON file off disk -- see load_catalog above."""
    path = Path(path)
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    return [FormationTemplate(**entry) for entry in raw]


def save_formation_catalog(templates: list[FormationTemplate], path: str | Path = DEFAULT_FORMATION_CATALOG_PATH) -> None:
    """Write the whole formation catalog back out to disk -- see save_catalog above."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(t) for t in templates], indent=2))


def find_formation(name: str, templates: list[FormationTemplate]) -> FormationTemplate | None:
    """Look up a formation template by name -- see _find_by_name."""
    return _find_by_name(name, templates)


DEFAULT_FOUNDATION_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "foundation_catalog.json"


@dataclass
class FoundationOption:
    """The "master record" for one named foundation type (e.g. "Strip
    Footings"): the standard write-up of that foundation type's
    requirements. Selected per-project by name lookup against
    ProjectInfo.recommended_foundations (report_io.py builds one
    FoundationSection per name in that list, matched the same forgiving
    way as everything else in this file). `name` is plugged into whichever
    heading wording report_io.py picks ("Recommended Foundation: X" for a
    single recommendation, "Option N - X" when there's more than one) --
    the "5.1"/"5.2" section number in front of it comes from a real Word
    auto-number field in the template itself, not from anything stored
    here, so renumbering the template or adding more options doesn't
    require touching this catalog.

    plain_paragraphs and list_paragraphs are kept separate because the
    report template renders them into two differently-formatted repeating
    blocks -- list_paragraphs keeps the source document's numbered-list
    styling, plain_paragraphs doesn't. Both are boilerplate a project's
    engineer is expected to review and adjust in the final draft, same as
    a project's soil descriptions."""

    name: str
    plain_paragraphs: list[str] = field(default_factory=list)
    list_paragraphs: list[str] = field(default_factory=list)


def load_foundation_catalog(path: str | Path = DEFAULT_FOUNDATION_CATALOG_PATH) -> list[FoundationOption]:
    """Read the foundation catalog JSON file off disk -- see load_catalog above."""
    path = Path(path)
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    return [FoundationOption(**entry) for entry in raw]


def save_foundation_catalog(options: list[FoundationOption], path: str | Path = DEFAULT_FOUNDATION_CATALOG_PATH) -> None:
    """Write the whole foundation catalog back out to disk -- see save_catalog above."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(o) for o in options], indent=2))


def find_foundation_option(name: str, options: list[FoundationOption]) -> FoundationOption | None:
    """Look up a foundation option by name -- see _find_by_name."""
    return _find_by_name(name, options)
