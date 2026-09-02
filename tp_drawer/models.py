"""Data model for a trial pit log project.

This file defines the shapes of the data that flow through the whole
program: a Project has some info about the job plus a list of TrialPits,
each of which has a list of soil Layers. Nothing in here does any real
work (no drawing, no file reading) -- it's just the "nouns" that the rest
of the codebase (excel_io.py, drawing.py, etc.) reads and writes.

ADVANCED TECHNIQUE -- @dataclass:
Every class below is decorated with @dataclass. Normally in Python you'd
have to hand-write an __init__ method that assigns every field
(`self.name = name`, `self.thickness_in = thickness_in`, ...), plus a
__repr__ if you want print(my_layer) to show something useful, plus an
__eq__ if you want two Layer objects with the same values to compare
equal. @dataclass generates all of that boilerplate for you automatically
just from the type-annotated fields listed in the class body. Think of it
like a form template: you declare "a Layer has these blanks to fill in"
and Python builds the machinery to create, print, and compare filled-in
forms for you.
"""

from dataclasses import asdict, dataclass, field
from decimal import Decimal

# The caption drawn under the last unit's landing when a pit's final soil
# layer wasn't identified on the input sheet (e.g. because the pit was
# abandoned before bedrock or a known formation was reached). See
# excel_io.py for where this gets overridden with a real formation name
# when one is provided -- in that case, termination_reason holds just the
# bare formation name (e.g. "IRONSHORE FORMATION MARL"), and drawing.py
# is what wraps it into a full caption ("IRONSHORE FORMATION MARL
# ENCOUNTERED AT DEPTH"). This default is used verbatim, with no wrapping,
# since there's no formation name to build a sentence around.
DEFAULT_TERMINATION_REASON = "TERMINATION STRATA UNDETERMINED"


@dataclass
class Layer:
    """One band of soil in a trial pit, e.g. "10 inches of Organic Topsoil"."""

    name: str
    thickness_in: Decimal
    description: str = ""


@dataclass
class TrialPit:
    """One excavated trial pit: an ordered stack of Layers from the ground
    surface downward, plus a few pit-level facts (groundwater depth, why
    digging stopped)."""

    number: str
    # ADVANCED TECHNIQUE -- field(default_factory=list):
    # You might expect `layers: list[Layer] = []` to work as a default, but
    # Python evaluates default values *once*, when the class is defined --
    # not once per new object. If the default were a literal `[]`, every
    # TrialPit you ever created would share the *same* list object, so
    # appending a layer to one pit would mysteriously appear in every other
    # pit too. default_factory=list tells @dataclass "call list() fresh for
    # each new TrialPit instead", giving every pit its own empty list.
    layers: list[Layer] = field(default_factory=list)
    groundwater_depth_in: Decimal | None = None
    termination_reason: str = DEFAULT_TERMINATION_REASON
    extra_note: str = ""

    @property
    def total_depth_in(self) -> Decimal:
        """The pit's total excavated depth: just the sum of every layer's
        thickness. Declared as a @property so callers can write
        `pit.total_depth_in` like a plain attribute instead of
        `pit.total_depth_in()` -- it's always kept in sync automatically
        because it's computed fresh from pit.layers every time it's read,
        rather than being a separate value that could drift out of date."""
        return sum((layer.thickness_in for layer in self.layers), Decimal(0))


@dataclass
class ProjectInfo:
    """Job-level metadata shown in the log's title block -- address, date,
    equipment used, who drew it, etc. -- shared by every pit in the project."""

    date: str = ""
    project_number: str = ""
    project_name: str = ""
    street_address: str = ""
    block_and_parcel: str = ""
    equipment_provider: str = ""
    equipment: str = ""
    drawn_by: str = "MAM"
    file_ref: str = ""
    scale_note: str = "N.T.S."


@dataclass
class Project:
    """The top-level object: one input workbook becomes one Project, which
    becomes one output PDF (one page per pit)."""

    info: ProjectInfo
    pits: list[TrialPit] = field(default_factory=list)


def project_to_dict(project: Project) -> dict:
    """Convert a Project into a plain dict of strings/numbers/lists/dicts --
    the only kinds of values the built-in `json` module knows how to write.

    This matters because our dataclasses use Decimal for measurements
    (chosen over `float` so that e.g. 3'-10" adds up exactly instead of
    picking up tiny binary-floating-point rounding errors), but Decimal
    isn't one of the types JSON understands. So every Decimal here gets
    converted to a str (e.g. "22") before going in the dict, and
    project_from_dict below converts it back to Decimal on the way in.

    Used by the webapp: after generating a log, the user can tweak a
    layer's description and see the PDF re-render. To do that, the
    project needs to be saved to disk between web requests (HTTP requests
    don't share memory) -- this function produces the dict that gets
    written out as project.json for that purpose.
    """
    return {
        "info": asdict(project.info),
        "pits": [
            {
                "number": pit.number,
                "layers": [
                    {"name": layer.name, "thickness_in": str(layer.thickness_in), "description": layer.description}
                    for layer in pit.layers
                ],
                "groundwater_depth_in": str(pit.groundwater_depth_in) if pit.groundwater_depth_in is not None else None,
                "termination_reason": pit.termination_reason,
                "extra_note": pit.extra_note,
            }
            for pit in project.pits
        ],
    }


def project_from_dict(data: dict) -> Project:
    """The reverse of project_to_dict: rebuild a real Project (with proper
    Decimal fields, not strings) from the plain dict that was loaded back
    out of project.json."""
    return Project(
        info=ProjectInfo(**data["info"]),
        pits=[
            TrialPit(
                number=pit["number"],
                layers=[
                    Layer(name=layer["name"], thickness_in=Decimal(layer["thickness_in"]), description=layer["description"])
                    for layer in pit["layers"]
                ],
                groundwater_depth_in=Decimal(pit["groundwater_depth_in"]) if pit["groundwater_depth_in"] is not None else None,
                termination_reason=pit["termination_reason"],
                extra_note=pit["extra_note"],
            )
            for pit in data["pits"]
        ],
    )
