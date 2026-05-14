from decimal import Decimal

from invest_note_api.utils.numbers import strip_comma_number


def test_string_with_commas_and_spaces():
    assert strip_comma_number("1,234,567") == "1234567"
    assert strip_comma_number("  1,234  ") == "1234"
    assert strip_comma_number(",,,") == ""


def test_empty_and_whitespace_string():
    assert strip_comma_number("") == ""
    assert strip_comma_number("   ") == ""


def test_string_without_commas_passthrough():
    assert strip_comma_number("123.45") == "123.45"
    assert strip_comma_number("abc") == "abc"


def test_non_string_passthrough():
    assert strip_comma_number(123) == 123
    assert strip_comma_number(123.45) == 123.45
    assert strip_comma_number(Decimal("1.5")) == Decimal("1.5")
    assert strip_comma_number(None) is None
    assert strip_comma_number(0) == 0
