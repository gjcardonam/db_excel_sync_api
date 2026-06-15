"""Concrete validation rules.

Each rule is small and focused. To add a new validation later, write a new
``ValidationRule`` subclass here and register it in ``registry.py``.
"""
from __future__ import annotations

import pandas as pd

from app.validation.base import (
    Severity,
    ValidationIssue,
    ValidationRule,
    format_labels,
)
from app.validation.constants import COPIAFORMATO


def _normalized_key_series(df: pd.DataFrame, key_column: str) -> pd.Series:
    return df[key_column].dropna().astype(str).str.strip()


class CopiaFormatoPresentRule(ValidationRule):
    """The reference row 'COPIAFORMATO' must be present as the first data row.

    Its absence means the user likely deleted or overwrote the template row,
    which can corrupt the expected format — so this is a blocking error.
    """

    code = "copiaformato_present"

    def validate(self, df, ctx):
        col = ctx.key_column
        if col not in df.columns:
            return [ValidationIssue(f"Missing required column '{col}'.", Severity.ERROR, self.code)]

        values = _normalized_key_series(df, col)
        if values.empty:
            return [ValidationIssue(f"Column '{col}' has no values.", Severity.ERROR, self.code)]

        if values.iloc[0].upper() != COPIAFORMATO:
            return [
                ValidationIssue(
                    f"The '{COPIAFORMATO}' reference row is missing or is not the first row of "
                    f"'{col}'. Do not delete or move it — always copy from it so the format is "
                    "not damaged.",
                    Severity.ERROR,
                    self.code,
                )
            ]
        return []


class RequiredColumnsRule(ValidationRule):
    """Every listed column must exist in the sheet."""

    code = "required_columns"

    def __init__(self, columns: list[str]):
        self.columns = columns

    def validate(self, df, ctx):
        return [
            ValidationIssue(f"Missing required column '{c}'.", Severity.ERROR, self.code)
            for c in self.columns
            if c not in df.columns
        ]


class NonNullValuesRule(ValidationRule):
    """Every listed (present) column must have a value on every row."""

    code = "non_null_values"

    def __init__(self, columns: list[str]):
        self.columns = columns

    def validate(self, df, ctx):
        issues: list[ValidationIssue] = []
        for c in self.columns:
            if c not in df.columns:
                continue
            missing = df[df[c].isna()]
            if not missing.empty:
                wells = format_labels(missing, ctx.key_column)
                issues.append(
                    ValidationIssue(f"Wells missing a value for '{c}': {wells}.", Severity.ERROR, self.code)
                )
        return issues


class TimestampRequiredRule(ValidationRule):
    """'time_stamp' must exist and be set on every row."""

    code = "timestamp_required"

    def __init__(self, column: str = "time_stamp"):
        self.column = column

    def validate(self, df, ctx):
        if self.column not in df.columns:
            return [ValidationIssue(f"Missing required column '{self.column}'.", Severity.ERROR, self.code)]
        missing = df[df[self.column].isna()]
        if not missing.empty:
            wells = format_labels(missing, ctx.key_column)
            return [ValidationIssue(f"Wells missing '{self.column}': {wells}.", Severity.ERROR, self.code)]
        return []


class Pump2CoefficientsRule(ValidationRule):
    """When a well has 'pump2', the second-pump coefficient columns are required."""

    code = "pump2_coefficients"

    def __init__(self, columns: list[str], flag_column: str = "pump2"):
        self.columns = columns
        self.flag_column = flag_column

    def validate(self, df, ctx):
        if self.flag_column not in df.columns or not df[self.flag_column].notna().any():
            return []

        issues: list[ValidationIssue] = []
        with_pump2 = df[df[self.flag_column].notna()]
        for c in self.columns:
            if c not in df.columns:
                issues.append(
                    ValidationIssue(
                        f"Missing required column '{c}' (required when '{self.flag_column}' is present).",
                        Severity.ERROR,
                        self.code,
                    )
                )
                continue
            missing = with_pump2[with_pump2[c].isna()]
            if not missing.empty:
                wells = format_labels(missing, ctx.key_column)
                issues.append(
                    ValidationIssue(
                        f"Wells with '{self.flag_column}' missing '{c}': {wells}.", Severity.ERROR, self.code
                    )
                )
        return issues


class DuplicateKeysRule(ValidationRule):
    """Warns when the key column repeats (only one row per key will survive upsert)."""

    code = "duplicate_keys"

    def validate(self, df, ctx):
        col = ctx.key_column
        if col not in df.columns:
            return []
        values = _normalized_key_series(df, col)
        duplicated = values[values.duplicated()].unique().tolist()
        if duplicated:
            shown = ", ".join(duplicated[:25])
            if len(duplicated) > 25:
                shown += f", … (+{len(duplicated) - 25} more)"
            return [
                ValidationIssue(
                    f"Duplicate '{col}' values found (only one row each will be kept): {shown}.",
                    Severity.WARNING,
                    self.code,
                )
            ]
        return []
