"""Parsing and formatting of feet-inches dimension strings, e.g. 3'-10\".

Everywhere else in the codebase, depths and thicknesses are stored as a
single Decimal number of total inches (e.g. 3'-10" is stored as 46). This
module is the only place that converts between that internal "total
inches" representation and the human-readable "3'-10"" text that appears
on the input spreadsheet and the output drawing. Keeping the conversion
in one place means if the input format ever needs to tolerate a new
variant (see the docstring below for the list it already tolerates), only
this file has to change.

WHY Decimal AND NOT float?
float uses binary floating point, which can't represent every decimal
value exactly -- 0.1 + 0.2 in Python gives 0.30000000000000004, not 0.3.
For a drawing tool where dimensions get added together repeatedly (layer
thicknesses stacking up into a total pit depth), those tiny errors could
accumulate into a visibly wrong number. Decimal represents numbers the
way you'd do the arithmetic by hand (base 10), so it doesn't have that
problem -- at the cost of being a bit slower, which doesn't matter here.
"""

import re
from decimal import Decimal, ROUND_HALF_UP

# A compiled regular expression (regex) that recognises feet-inches text
# like 3'-10". Compiling it once at import time (rather than re-parsing
# the pattern string every time parse_feet_inches runs) is a small
# performance habit -- the pattern itself only needs to be built once.
# Named groups -- (?P<feet>...) and (?P<inches>...) -- let the code below
# pull out "feet" and "inches" by name instead of by fragile numbered
# position, so the pattern can be tweaked without breaking the code that
# reads it.
_FEET_INCHES_RE = re.compile(
    r"""^\s*(?P<feet>\d+)\s*'\s*-?\s*(?:(?P<inches>\d+(?:\.\d+)?)\s*"?)?\s*$"""
)


def parse_feet_inches(text: str, *, context: str = "") -> Decimal:
    """Parse a feet-inches string like 3'-10", 3'-5, 7'-2", or 5' into total inches.

    Tolerates a missing trailing double-quote, missing dash, extra whitespace,
    decimal inches, and an omitted inches component.
    """
    match = _FEET_INCHES_RE.match(text or "")
    if not match:
        # `context` lets a caller pass in something like "Trial Pit 3,
        # Topsoil layer" so the error message says exactly which cell in
        # the spreadsheet was unreadable, instead of just repeating the
        # raw text back with no clue where it came from.
        suffix = f" ({context})" if context else ""
        raise ValueError(f"Cannot parse feet-inches value {text!r}{suffix}")
    feet = Decimal(match.group("feet"))
    # `or "0"` covers the case where the inches part was omitted entirely
    # (e.g. someone just wrote "5'") -- group("inches") is None then, and
    # Decimal(None) would raise, so we fall back to the string "0" first.
    inches = Decimal(match.group("inches") or "0")
    return feet * 12 + inches


def format_feet_inches(total_inches: Decimal) -> str:
    """Format total inches back into a X'-Y\" label for drawing."""
    # Round to the nearest whole inch before splitting into feet/inches --
    # ROUND_HALF_UP means "0.5 always rounds up", matching how most people
    # round by hand (as opposed to Python's own round(), which rounds 0.5
    # to the nearest *even* number -- a surprising trap here).
    total = int(total_inches.to_integral_value(rounding=ROUND_HALF_UP))
    # divmod(total, 12) does one division and gives back both the
    # quotient and the remainder in a single call: e.g. divmod(46, 12) ->
    # (3, 10), i.e. 46 inches is 3 feet with 10 inches left over.
    feet, inches = divmod(total, 12)
    return f'{feet}\'-{inches}"'
