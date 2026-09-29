"""Read/write the trial pit input workbook.

The sheet is label-driven, not position-hardcoded: pit count, layer count,
and layer names are all discovered from the sheet content, mirroring the
user's existing "Form Inputs" layout (header fields, then a table keyed by
"Trial pit" with one row per soil layer and a trailing groundwater row).

WHY "LABEL-DRIVEN, NOT POSITION-HARDCODED" MATTERS:
An easier-to-write version of this module could just say "the date is
always in cell B1, pit 1's topsoil thickness is always in cell B9", and
so on. That would break the moment someone inserts a row, adds a 5th
pit, or renames/reorders a layer in their spreadsheet -- extremely easy
things for a non-programmer to accidentally do. Instead, every function
below *searches* for cells by reading their text labels (e.g. it scans
column A looking for the row whose label says "Groundwater", wherever
that row happens to be) so the workbook's exact row/column layout can
shift around freely and the reader still finds the right data.
"""

import datetime
import re
from decimal import Decimal
from pathlib import Path

import openpyxl

from tp_drawer.models import DEFAULT_TERMINATION_REASON, Layer, Project, ProjectInfo, TrialPit
from tp_drawer.units import parse_feet_inches

# Maps a lowercased label as it appears in column A of the spreadsheet
# (e.g. "Street Address") to the ProjectInfo attribute name it fills in
# (e.g. "street_address"). Having this mapping as one dict, rather than a
# chain of if/elif checks, makes it a single place to look to see every
# header field the reader understands, and to add a new one.
#
# These are the fields the trial pit log drawing actually needs, so a
# sheet missing any of them is rejected outright (see _build_project_info).
_HEADER_ALIASES = {
    "date": "date",
    "project number": "project_number",
    "project name": "project_name",
    "street address": "street_address",
    "block and parcel": "block_and_parcel",
    "equipment provider": "equipment_provider",
    "equipment": "equipment",
}
# Extra header fields that only the geotechnical report (report_io.py)
# uses -- optional, so a sheet from before the report feature existed
# still loads fine; a missing one just comes back as "". Note the sheet
# label "AMR Engineer" doesn't lowercase-match its attribute name the way
# the required fields above do, hence this being a separate dict rather
# than just folding these into _HEADER_ALIASES.
_OPTIONAL_HEADER_ALIASES = {
    "client": "client",
    "amr engineer": "engineer_name",
    "site work completion date": "site_work_completion_date",
    "proposed structure/s": "proposed_structures",
}
# Header labels (besides "date") whose cell value should get the same
# datetime -> "23-May-2026" treatment in _format_header_value.
_DATE_LABELS = {"date", "site work completion date"}
# Words a user might type in the groundwater cell to mean "we dug the pit
# and didn't hit water" -- treated as "no depth recorded" rather than
# text we'd try (and fail) to parse as a feet-inches measurement.
_NOT_ENCOUNTERED_TOKENS = {"-", "n/a", "na", "none"}
# Matches a trailing parenthesised note on a layer-name label, e.g. turns
# "Topsoil\n(Layer thickness)" into just "Topsoil" once substituted away.
# \s*\(.*?\)\s*$ reads as: optional whitespace, then an opening
# parenthesis, then anything at all (the .*? is "as few characters as
# possible" so it stops at the *first* closing paren rather than
# swallowing past it if there were ever two groups), then a closing
# parenthesis, then optional trailing whitespace, anchored to the end of
# the string ($). re.DOTALL makes "." also match newline characters,
# since the label has a literal line break before the "(Layer
# thickness)" part.
_LAYER_ANNOTATION_RE = re.compile(r"\s*\(.*?\)\s*$", re.DOTALL)


def _norm(text: str) -> str:
    """Normalise a label for comparison: trim whitespace, drop an optional
    trailing colon (so "Date" and "Date:" are treated the same), and
    lowercase it. Every label lookup in this file runs through here first
    so comparisons never fail over trivial formatting differences."""
    return text.strip().rstrip(":").strip().lower()


def _clean_layer_name(raw: str) -> str:
    """Strip the "(Layer thickness)"-style hint text off a layer label,
    leaving just the soil unit name (e.g. "Topsoil") to store on the
    Layer object and later look up in the unit catalog."""
    return _LAYER_ANNOTATION_RE.sub("", raw).strip()


def _format_header_value(label_key: str, value) -> str:
    """Turn one header cell's raw value into the text stored on
    ProjectInfo. Every header field except "date" just gets stringified
    as-is (see the WHY below) -- "date" gets special treatment because of
    what a date-formatted Excel cell actually contains.

    WHY DATE NEEDS SPECIAL HANDLING:
    When a spreadsheet cell is formatted as a date (Excel's normal
    behaviour when you type something like 23/05/2026 into it), openpyxl
    doesn't hand back the text "23/05/2026" -- it hands back a real
    Python datetime.datetime object. Calling plain str() on that object
    would print "2026-05-23 00:00:00" (ISO format, with the always-present
    but meaningless midnight time tacked on) rather than anything
    resembling what was actually typed into the cell. isinstance(value,
    datetime.date) catches that case (datetime.datetime is itself a
    subclass of datetime.date, so this one check covers both), and
    value.strftime("%d-%B-%Y") reformats it into "23-May-2026" instead --
    %d is the zero-padded day, %B is the full month name, %Y is the
    4-digit year.

    If the Date cell was instead entered as plain text (not
    date-formatted), `value` is already a string, isinstance(...) is
    False, and this falls through to the same plain str(value).strip()
    every other header field uses -- so a hand-typed date like "May 2026"
    or "TBD" still comes through unchanged rather than being forced into
    a format it doesn't fit.
    """
    if value is None:
        return ""
    if label_key in _DATE_LABELS and isinstance(value, datetime.date):
        return value.strftime("%d-%B-%Y")
    return str(value).strip()


def _read_header_and_pit_row(ws) -> tuple[dict[str, str], int]:
    """Scan down column A collecting label/value pairs (Date, Project
    Number, ...) until it finds the row labelled "Trial pit" -- that row
    is the header for the per-pit data table below it, so this returns
    both what it collected *and* which row number that boundary is, so
    the caller knows where to start reading the table from.
    """
    header_fields: dict[str, str] = {}
    # range(1, 201) means "try rows 1 through 200" -- a generous but
    # finite search limit, so a malformed sheet with no "Trial pit" row
    # at all eventually falls through to the ValueError below instead of
    # scanning forever.
    for row in range(1, 201):
        label = ws.cell(row=row, column=1).value
        if label is None or str(label).strip() == "":
            # Blank row in column A -- just skip past it and keep looking,
            # rather than treating it as the end of the header section.
            continue
        if _norm(str(label)) == "trial pit":
            # Found the boundary row: stop collecting header fields and
            # hand back what we have, plus this row number.
            return header_fields, row
        value = ws.cell(row=row, column=2).value
        header_fields[_norm(str(label))] = _format_header_value(_norm(str(label)), value)
    raise ValueError("Could not find a 'Trial pit' header row in the input sheet")


def _build_project_info(header_fields: dict[str, str]) -> ProjectInfo:
    """Turn the raw {label: value} dict collected above into a proper
    ProjectInfo object, checking first that every field the drawing code
    actually needs was present on the sheet."""
    # A list comprehension: read as "for each label in _HEADER_ALIASES,
    # keep it if it's *not* a key in header_fields". This is a compact way
    # of writing a `for` loop that builds up a list of just the entries
    # matching some condition.
    missing = [label for label in _HEADER_ALIASES if label not in header_fields]
    if missing:
        raise ValueError(f"Missing required header field(s) in input sheet: {', '.join(missing)}")
    # Build a dict of {ProjectInfo attribute name: value}, then unpack it
    # into ProjectInfo(**kwargs) -- same "unpack a dict into keyword
    # arguments" trick used in catalog.py's load_catalog.
    kwargs = {attr: header_fields[label] for label, attr in _HEADER_ALIASES.items()}
    # Optional report-only fields: pulled in only if the sheet actually has
    # them (see _OPTIONAL_HEADER_ALIASES above) -- absent ones just leave
    # ProjectInfo's own "" default in place.
    kwargs.update({attr: header_fields[label] for label, attr in _OPTIONAL_HEADER_ALIASES.items() if label in header_fields})
    info = ProjectInfo(**kwargs)
    if not info.file_ref:
        # file_ref isn't its own header field on the sheet -- if it comes
        # back blank, fall back to reusing the project number so the
        # title block always has *something* to show.
        info.file_ref = info.project_number
    return info


def _read_pit_columns(ws, header_row: int) -> list[tuple[int, str]]:
    """Walk rightward along the "Trial pit" header row, collecting
    (column_number, pit_label) pairs for every pit column, stopping at
    the first empty cell -- that's what lets the sheet have any number of
    pits (1, 4, 12, ...) without the code needing to be told the count in
    advance."""
    columns: list[tuple[int, str]] = []
    for col in range(2, 61):  # column 1 is the row's own label, so pit columns start at 2
        value = ws.cell(row=header_row, column=col).value
        if value is None or str(value).strip() == "":
            # First empty cell marks the end of the pit columns.
            break
        columns.append((col, str(value).strip()))
    if not columns:
        raise ValueError("No trial pit columns found next to the 'Trial pit' header row")
    return columns


def _find_table_rows(ws, header_row: int) -> tuple[list[int], int, int | None, int | None]:
    """Below the "Trial pit" header row, every row is either a soil layer
    (until we hit "Groundwater") or, a little further down, one or more
    optional rows: "Final Strata" (what was found at the base of the pit)
    and "Pit walls stable?" (whether the excavation stayed structurally
    sound). Returns (list of layer row numbers, the groundwater row
    number, the final-strata row number or None, the walls-stable row
    number or None)."""
    layer_rows: list[int] = []
    groundwater_row: int | None = None
    for row in range(header_row + 1, header_row + 61):
        label = ws.cell(row=row, column=1).value
        if label is None or str(label).strip() == "":
            continue
        if "groundwater" in _norm(str(label)):
            groundwater_row = row
            # Stop collecting layer rows the moment we hit the
            # groundwater row -- everything above it (that had a label)
            # is a soil layer, and we don't want to keep scanning past it
            # into unrelated content further down the sheet.
            break
        layer_rows.append(row)
    if groundwater_row is None:
        raise ValueError("Could not find a 'Groundwater' row in the input sheet")

    # "Final Strata" is optional and, if present, lives a few rows below
    # groundwater -- search a small fixed window (5 rows) rather than the
    # sheet's full remaining length, since this field is expected to sit
    # right after groundwater or not exist at all.
    final_strata_row: int | None = None
    for row in range(groundwater_row + 1, groundwater_row + 6):
        label = ws.cell(row=row, column=1).value
        if label is not None and "final strata" in _norm(str(label)):
            final_strata_row = row
            break

    # "Pit walls stable?" is likewise optional -- searched over a wider
    # window than Final Strata since it's a newer field with no fixed
    # position relative to it (a sheet might list it before or after
    # Final Strata/Final Depth).
    walls_stable_row: int | None = None
    for row in range(groundwater_row + 1, groundwater_row + 10):
        label = ws.cell(row=row, column=1).value
        if label is not None and "pit walls stable" in _norm(str(label)):
            walls_stable_row = row
            break

    return layer_rows, groundwater_row, final_strata_row, walls_stable_row


# Matches a label like "Option 1", "Option 2", ... "Option 12" (as on the
# reference "Project Data.xlsx" sheet, which has a "Recommended
# Foundation:" section with one "Option N:" row per candidate foundation
# system after the trial pit data). Open-ended (any number, not just 1 and
# 2) for the same reason pit columns and layer rows aren't hardcoded to a
# fixed count elsewhere in this file -- a project might recommend a third
# option someday, and the sheet shouldn't need code changes to support it.
_OPTION_LABEL_RE = re.compile(r"^option\s+(\d+)$")


def _read_recommended_foundations(ws, start_row: int) -> list[str]:
    """Best-effort scan of the rows below the per-pit table for "Option N:"
    rows, returning their values in Option-number order with any blank
    ones dropped (e.g. a sheet with "Option 1: Strip Footings" and an
    empty "Option 2:" yields just ["Strip Footings"]). Unlike
    _read_header_and_pit_row, this has no boundary row to stop at, so it
    just walks a generous fixed window -- a sheet with no such rows at all
    (e.g. one from before the report feature existed) yields an empty
    list rather than an error."""
    numbered_values: list[tuple[int, str]] = []
    for row in range(start_row, start_row + 100):
        label = ws.cell(row=row, column=1).value
        if label is None or str(label).strip() == "":
            continue
        match = _OPTION_LABEL_RE.match(_norm(str(label)))
        if match is None:
            continue
        value = ws.cell(row=row, column=2).value
        text = _format_header_value("option", value)
        if text:
            numbered_values.append((int(match.group(1)), text))
    numbered_values.sort(key=lambda pair: pair[0])
    return [text for _, text in numbered_values]


# Matches a label like "Trial Pit 1:" or "Trial Pit 12:" under the sheet's
# "Notes:" section -- one row per pit, the pit number embedded in the
# label itself rather than the row living in a per-pit column the way the
# main soil-layer table does. t(?:ri|ir)al (not just "trial") tolerates
# "Tiral Pit 1:" -- a typo that recurs consistently across this
# practice's own input sheets (seen on more than one real project), so
# it's treated as an expected spelling rather than a sheet error.
_PIT_NOTE_LABEL_RE = re.compile(r"^t(?:ri|ir)al\s+pit\s+(\d+)$")


def _read_pit_notes(ws, start_row: int) -> dict[str, str]:
    """Best-effort scan of the rows below the per-pit table for "Trial Pit
    N:"/"Tiral Pit N:" rows, returning {pit_number: note_text}. Same
    "generous fixed window, no boundary row" approach as
    _read_recommended_foundations above, for the same reason: a sheet
    with no such rows at all (there's never been a note worth recording,
    or the sheet predates this field) should just yield an empty dict
    rather than an error."""
    notes: dict[str, str] = {}
    for row in range(start_row, start_row + 100):
        label = ws.cell(row=row, column=1).value
        if label is None or str(label).strip() == "":
            continue
        match = _PIT_NOTE_LABEL_RE.match(_norm(str(label)))
        if match is None:
            continue
        value = ws.cell(row=row, column=2).value
        if value is not None and str(value).strip() != "":
            notes[match.group(1)] = str(value).strip()
    return notes


def _parse_walls_stable(value) -> bool:
    """Reads the "Pit walls stable?" cell: "Yes" -> True, "No" -> False,
    matched case-insensitively/trimmed the same way every other label/
    token comparison in this file is (see _norm). A blank cell, or any
    other text that isn't recognizably "yes"/"no", defaults to True
    (stable) rather than raising -- the same "don't fail a sheet over an
    optional field" treatment _parse_optional_depth gives groundwater."""
    if value is None:
        return True
    text = _norm(str(value))
    if text == "no":
        return False
    return True


def _parse_optional_depth(value, coordinate: str) -> Decimal | None:
    """Like units.parse_feet_inches, but for a cell that's allowed to be
    blank or say "-"/"N/A" (meaning "groundwater wasn't encountered") --
    those cases return None instead of raising an error, since a missing
    groundwater reading is valid input, not a mistake."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or _norm(text) in _NOT_ENCOUNTERED_TOKENS:
        return None
    return parse_feet_inches(text, context=coordinate)


def read_project(path: str | Path) -> Project:
    """The main entry point of this module: load an .xlsx file off disk and
    turn it into a fully-populated Project object. Everything above this
    function is a small helper it calls in sequence -- find the header,
    find the pit columns, find the table rows, then loop over every
    (pit, layer) cell to build up the data."""
    # data_only=True tells openpyxl to give us the last *calculated*
    # value of any formula cells (e.g. what Excel most recently computed
    # for "=B2+B3"), rather than the literal formula text itself -- we
    # want the number, not the recipe for the number.
    wb = openpyxl.load_workbook(path, data_only=True)
    # .active is whichever sheet was selected/visible when the workbook
    # was last saved -- this tool expects a single-sheet input, so it
    # doesn't need to search by sheet name.
    ws = wb.active

    header_fields, header_row = _read_header_and_pit_row(ws)
    info = _build_project_info(header_fields)
    pit_columns = _read_pit_columns(ws, header_row)
    # ADVANCED TECHNIQUE -- multiple return values via a tuple:
    # _find_table_rows returns four different pieces of information
    # packed into one tuple; writing `a, b, c, d = some_function(...)`
    # unpacks them into four separate names in one line, which reads
    # more clearly than reaching into a tuple by numeric index
    # (result[0], result[1], result[2], result[3]).
    layer_rows, groundwater_row, final_strata_row, walls_stable_row = _find_table_rows(ws, header_row)

    # Where the per-pit table ends and any optional sections below it
    # (Recommended Foundation, Notes) begin -- the highest of the three
    # optional/required row numbers just found, since a sheet can order
    # Final Strata and Pit Walls Stable? either way (walls_stable_row's
    # own search window already tolerates that -- see _find_table_rows --
    # so this can't just assume final_strata_row is always the later one).
    post_table_row = max(row for row in (groundwater_row, final_strata_row, walls_stable_row) if row is not None) + 1

    info.recommended_foundations = _read_recommended_foundations(ws, post_table_row)
    pit_notes = _read_pit_notes(ws, post_table_row)

    pits: list[TrialPit] = []
    # Outer loop: once per pit column (left to right across the sheet).
    for col, pit_number in pit_columns:
        layers: list[Layer] = []
        # Inner loop: once per soil-layer row, for *this* pit's column --
        # so the two loops together visit every cell in the data table,
        # row by row within each column.
        for row in layer_rows:
            raw_label = ws.cell(row=row, column=1).value
            layer_name = _clean_layer_name(str(raw_label))
            cell = ws.cell(row=row, column=col)
            if cell.value is None or str(cell.value).strip() == "":
                # This pit doesn't have this layer (e.g. pit 1 has no Peat
                # layer) -- an empty cell means "skip it", not "zero
                # thickness", so nothing gets appended for this row.
                continue
            thickness = parse_feet_inches(str(cell.value), context=cell.coordinate)
            layers.append(Layer(name=layer_name, thickness_in=thickness))

        gw_cell = ws.cell(row=groundwater_row, column=col)
        groundwater_depth_in = _parse_optional_depth(gw_cell.value, gw_cell.coordinate)

        # Default assumption if there's no "Final Strata" info at all for
        # this pit; overwritten below only if the sheet actually names one.
        # Stored as just the bare formation name (uppercased), not a full
        # sentence -- drawing.py is what wraps it into the caption shown
        # on the log, so this module only has to worry about *what* the
        # formation is called, not how it reads as a sentence.
        termination_reason = DEFAULT_TERMINATION_REASON
        if final_strata_row is not None:
            strata_cell = ws.cell(row=final_strata_row, column=col)
            strata_value = strata_cell.value
            if strata_value is not None and str(strata_value).strip() != "":
                termination_reason = str(strata_value).strip().upper()

        walls_stable = True
        if walls_stable_row is not None:
            walls_stable = _parse_walls_stable(ws.cell(row=walls_stable_row, column=col).value)

        pits.append(
            TrialPit(
                number=pit_number,
                layers=layers,
                groundwater_depth_in=groundwater_depth_in,
                termination_reason=termination_reason,
                walls_stable=walls_stable,
                extra_note=pit_notes.get(pit_number, ""),
            )
        )

    return Project(info=info, pits=pits)


def write_template(
    path: str | Path,
    num_pits: int = 4,
    layer_names: tuple[str, ...] = ("Topsoil", "Peat", "Beach Sand"),
) -> None:
    """The opposite direction of read_project: generate a *blank* input
    workbook laid out the way this module expects to read one back --
    handy both as a starting point for a new user and, implicitly, as a
    guarantee that this module can always read its own output."""
    wb = openpyxl.Workbook()
    ws = wb.active

    header_labels = [
        "Date",
        "Project Number",
        "Project Name",
        "Street Address",
        "Block and Parcel",
        "Equipment Provider",
        "Equipment",
    ]
    # enumerate(header_labels, start=1) hands back (1, "Date"), (2,
    # "Project Number"), ... -- pairing each label with its row number
    # without having to separately track and increment a counter variable.
    for row, label in enumerate(header_labels, start=1):
        ws.cell(row=row, column=1, value=label)

    # Leave one blank row (the "+ 2" rather than "+ 1") between the last
    # header field and the "Trial pit" row, purely for readability when a
    # person opens the sheet in Excel.
    pit_header_row = len(header_labels) + 2
    ws.cell(row=pit_header_row, column=1, value="Trial pit")
    for i in range(num_pits):
        # Pit numbers are written starting at column 2 (column 1 is
        # reserved for row labels), so pit i (0-based) lands in column
        # 2 + i, and is itself labelled i + 1 (1-based, matching how
        # pits are numbered on the actual drawing).
        ws.cell(row=pit_header_row, column=2 + i, value=i + 1)

    # Plain loop with a manually-incremented `row` counter (rather than
    # enumerate) because the row number needs to keep climbing *after*
    # this loop too, for the Groundwater row that follows it.
    row = pit_header_row + 1
    for name in layer_names:
        ws.cell(row=row, column=1, value=f"{name}\n(Layer thickness)")
        row += 1

    ws.cell(row=row, column=1, value="Groundwater\n(depth below grade level)")

    ws.column_dimensions["A"].width = 32
    for col in range(2, 2 + num_pits):
        # openpyxl addresses columns by number internally (2, 3, 4, ...)
        # but column *widths* are set via the spreadsheet's familiar
        # letter names ("B", "C", "D", ...) -- get_column_letter converts
        # between the two.
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 12

    wb.save(path)
