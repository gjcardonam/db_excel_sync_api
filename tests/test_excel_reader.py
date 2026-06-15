import math
from datetime import datetime

from app.utils.excel_reader import to_float_from_excel


def test_comma_decimal_is_parsed():
    assert to_float_from_excel("1,5") == 1.5


def test_dot_decimal_is_parsed():
    assert to_float_from_excel("2.0") == 2.0


def test_plain_number():
    assert to_float_from_excel(3) == 3.0


def test_invalid_value_returns_nan():
    assert math.isnan(to_float_from_excel("not-a-number"))


def test_datetime_is_converted_to_excel_serial():
    # 1899-12-30 is Excel serial 0, so the next day must be 1.0.
    assert to_float_from_excel(datetime(1899, 12, 31)) == 1.0
