"""Drawing configuration: page size, company branding, logo."""

from dataclasses import dataclass, field
from pathlib import Path

# __file__ is this module's own path (config.py). .resolve() turns it into
# a full, unambiguous absolute path; .parent goes up one folder (out of
# tp_drawer/) and .parent again goes up one more (to the project root), so
# this always finds reference/AMR_Logo.jpg relative to where the *code*
# lives -- not relative to whatever folder the program happened to be
# launched from, which could be anywhere.
_DEFAULT_LOGO_PATH = Path(__file__).resolve().parent.parent / "reference" / "AMR_Logo.jpg"


@dataclass
class Config:
    """Knobs for how a log gets drawn, as opposed to *what* gets drawn
    (that's the Project in models.py). Created once per render and passed
    down through drawing.py; every field has a sensible default so most
    callers can just write Config() and get the standard AMR-branded
    letter-size page."""

    page_size_in: tuple[float, float] = (11.0, 8.5)  # US Letter landscape
    company_name: str = "AMR CONSULTING ENGINEERS"
    # ADVANCED TECHNIQUE -- field(default_factory=lambda: ...):
    # Same reasoning as TrialPit.layers in models.py: a Path object is
    # mutable-ish/shared state, so @dataclass won't let you write
    # `logo_path: Path | None = _DEFAULT_LOGO_PATH` directly as a default
    # (it deliberately raises an error to stop you from accidentally
    # sharing one mutable object across every Config). Wrapping it in a
    # zero-argument lambda and passing that as default_factory tells
    # @dataclass "call this function to produce a fresh default each
    # time" instead. Here the "fresh" value is the same path every time
    # anyway (Path objects are effectively read-only in practice), so
    # this is really just satisfying @dataclass's safety check rather
    # than avoiding a real bug -- but it's the standard pattern regardless.
    logo_path: Path | None = field(default_factory=lambda: _DEFAULT_LOGO_PATH)
