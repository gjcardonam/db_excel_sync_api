import pandas as pd

from app.services.excel_processor import (
    REQUIRED_PUMP_COEFFICIENTS,
    PUMP2_COEFFICIENTS,
    validate_pump_coefficients,
)


def _base_df():
    data = {"well": ["W1"], "time_stamp": ["2020-01-01"]}
    for col in REQUIRED_PUMP_COEFFICIENTS:
        data[col] = [1.0]
    return pd.DataFrame(data)


def test_valid_dataframe_has_no_errors():
    assert validate_pump_coefficients(_base_df()) == []


def test_missing_timestamp_column_is_reported():
    df = _base_df().drop(columns=["time_stamp"])
    errors = validate_pump_coefficients(df)
    assert any("time_stamp" in e for e in errors)


def test_missing_required_coefficient_is_reported():
    df = _base_df().drop(columns=["x5"])
    errors = validate_pump_coefficients(df)
    assert any("x5" in e for e in errors)


def test_null_coefficient_value_is_reported():
    df = _base_df()
    df.loc[0, "x4"] = None
    errors = validate_pump_coefficients(df)
    assert any("x4" in e for e in errors)


def test_pump2_requires_extra_coefficients():
    df = _base_df()
    df["pump2"] = ["P2"]
    errors = validate_pump_coefficients(df)
    # All PUMP2 coefficient columns are missing, so each should be flagged.
    assert any(PUMP2_COEFFICIENTS[0] in e for e in errors)
