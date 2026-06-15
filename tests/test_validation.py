import pandas as pd

from app.validation import (
    REQUIRED_PUMP_COEFFICIENTS,
    Severity,
    ValidationContext,
    Validator,
    data_validator,
    template_validator,
)
from app.validation.rules import (
    CopiaFormatoPresentRule,
    DuplicateKeysRule,
    Pump2CoefficientsRule,
)

ESP_CTX = ValidationContext(company="ACME", key_column="well", lift_method="ESP", sheet="ESP")


def _valid_esp_df(include_copiaformato=True):
    rows = []
    if include_copiaformato:
        rows.append("COPIAFORMATO")
    rows.append("W1")
    data = {"well": rows, "time_stamp": ["2020-01-01"] * len(rows)}
    for col in REQUIRED_PUMP_COEFFICIENTS:
        data[col] = [1.0] * len(rows)
    return pd.DataFrame(data)


# --- COPIAFORMATO rule ---

def test_copiaformato_present_passes():
    df = _valid_esp_df(include_copiaformato=True)
    issues = CopiaFormatoPresentRule().validate(df, ESP_CTX)
    assert issues == []


def test_copiaformato_missing_is_error():
    df = _valid_esp_df(include_copiaformato=False)
    issues = CopiaFormatoPresentRule().validate(df, ESP_CTX)
    assert len(issues) == 1
    assert issues[0].severity is Severity.ERROR
    assert "COPIAFORMATO" in issues[0].message


def test_copiaformato_not_first_is_error():
    df = pd.DataFrame({"well": ["W1", "COPIAFORMATO"], "time_stamp": ["x", "y"]})
    issues = CopiaFormatoPresentRule().validate(df, ESP_CTX)
    assert issues and issues[0].severity is Severity.ERROR


def test_template_validator_flags_missing_copiaformato():
    df = _valid_esp_df(include_copiaformato=False)
    issues = template_validator(ESP_CTX).validate(df, ESP_CTX)
    assert Validator.errors(issues)


# --- ESP data rules (run on data without the COPIAFORMATO row) ---

def test_data_validator_passes_for_valid_esp():
    df = _valid_esp_df(include_copiaformato=False)
    issues = data_validator(ESP_CTX).validate(df, ESP_CTX)
    assert Validator.errors(issues) == []


def test_data_validator_flags_missing_coefficient_column():
    df = _valid_esp_df(include_copiaformato=False).drop(columns=["x5"])
    issues = data_validator(ESP_CTX).validate(df, ESP_CTX)
    assert any("x5" in i.message for i in Validator.errors(issues))


def test_data_validator_flags_null_coefficient_value():
    df = _valid_esp_df(include_copiaformato=False)
    df.loc[df.index[-1], "x4"] = None
    issues = data_validator(ESP_CTX).validate(df, ESP_CTX)
    assert any("x4" in i.message for i in Validator.errors(issues))


def test_data_validator_flags_missing_timestamp():
    df = _valid_esp_df(include_copiaformato=False).drop(columns=["time_stamp"])
    issues = data_validator(ESP_CTX).validate(df, ESP_CTX)
    assert any("time_stamp" in i.message for i in Validator.errors(issues))


# --- pump2 conditional rule ---

def test_pump2_requires_extra_columns():
    df = _valid_esp_df(include_copiaformato=False)
    df["pump2"] = ["P2"]
    issues = Pump2CoefficientsRule(["x52x"]).validate(df, ESP_CTX)
    assert any("x52x" in i.message for i in issues)


def test_pump2_absent_means_no_issues():
    df = _valid_esp_df(include_copiaformato=False)
    issues = Pump2CoefficientsRule(["x52x"]).validate(df, ESP_CTX)
    assert issues == []


# --- duplicates are a WARNING, not an error ---

def test_duplicate_keys_is_warning():
    df = pd.DataFrame({"well": ["W1", "W1", "W2"]})
    issues = DuplicateKeysRule().validate(df, ESP_CTX)
    assert len(issues) == 1
    assert issues[0].severity is Severity.WARNING
    assert "W1" in issues[0].message


# --- GL currently has no blocking data rules ---

def test_gl_has_no_blocking_data_rules_yet():
    ctx = ValidationContext(company="ACME", key_column="well", lift_method="GL", sheet="GAS LIFT")
    df = pd.DataFrame({"well": ["W1", "W2"]})
    issues = data_validator(ctx).validate(df, ctx)
    assert Validator.errors(issues) == []
