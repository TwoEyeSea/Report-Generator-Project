"""Persistent database of subsurface unit templates (name + description).

Templates are the source of truth for a unit's boilerplate description text.
`hydrate_descriptions` copies a matching template's text into a project's
Layer objects -- from that point on, editing a project's descriptions never
touches the template store.
"""

import json
from dataclasses import asdict, dataclass
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


def find_template(name: str, templates: list[UnitTemplate]) -> UnitTemplate | None:
    """Look up a template by name, ignoring case and stray leading/trailing
    spaces (so "Clay", " CLAY ", and "clay" all match the same template --
    forgiving of small inconsistencies in how a name was typed on the
    input spreadsheet). Returns None, rather than raising an error, when
    nothing matches -- callers are expected to handle "no template for
    this unit" as a normal, non-exceptional case."""
    key = name.strip().lower()
    for template in templates:
        if template.name.strip().lower() == key:
            return template
    return None


def hydrate_descriptions(project: Project, templates: list[UnitTemplate]) -> None:
    """Copy each layer's matching template description in, if the layer doesn't
    already carry one. Never writes back to `templates` -- a one-way copy."""
    for pit in project.pits:
        for layer in pit.layers:
            if layer.description:
                # This layer already has its own description (e.g. typed
                # in by the user, or hydrated on a previous run) -- leave
                # it alone rather than clobbering it with the generic
                # catalog text.
                continue
            template = find_template(layer.name, templates)
            if template is not None:
                layer.description = template.description
