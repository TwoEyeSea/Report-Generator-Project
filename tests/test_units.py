from decimal import Decimal

import pytest

from tp_drawer.units import format_feet_inches, parse_feet_inches


@pytest.mark.parametrize(
    "text, expected_inches",
    [
        ("3'-10\"", 46),
        ("3'-5", 41),  # missing trailing quote, as seen in real input data
        ("7'-2\"", 86),
        ("4'-0\"", 48),
        ("5'", 60),
        (" 3' - 10\" ", 46),  # extra whitespace
        ("2'-1\"", 25),
    ],
)
def test_parse_feet_inches_valid(text, expected_inches):
    assert parse_feet_inches(text) == Decimal(expected_inches)


@pytest.mark.parametrize("text", ["", "n/a", "not a dimension", "3 feet"])
def test_parse_feet_inches_invalid(text):
    with pytest.raises(ValueError):
        parse_feet_inches(text)


def test_parse_feet_inches_error_includes_context():
    with pytest.raises(ValueError, match="D9"):
        parse_feet_inches("bogus", context="D9")


@pytest.mark.parametrize(
    "inches, expected",
    [
        (Decimal(46), "3'-10\""),
        (Decimal(41), "3'-5\""),
        (Decimal(0), "0'-0\""),
        (Decimal(60), "5'-0\""),
    ],
)
def test_format_feet_inches(inches, expected):
    assert format_feet_inches(inches) == expected


def test_round_trip():
    original = "3'-10\""
    assert format_feet_inches(parse_feet_inches(original)) == original
