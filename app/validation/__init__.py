"""Extensible, rule-based data validation framework."""
from app.validation.base import (
    Severity,
    ValidationContext,
    ValidationIssue,
    ValidationRule,
    Validator,
)
from app.validation.constants import (
    COPIAFORMATO,
    NUMERIC_COLS,
    PUMP2_COEFFICIENTS,
    REQUIRED_PUMP_COEFFICIENTS,
)
from app.validation.exceptions import ExcelValidationError
from app.validation.registry import data_validator, template_validator

__all__ = [
    "Severity",
    "ValidationContext",
    "ValidationIssue",
    "ValidationRule",
    "Validator",
    "ExcelValidationError",
    "data_validator",
    "template_validator",
    "COPIAFORMATO",
    "NUMERIC_COLS",
    "REQUIRED_PUMP_COEFFICIENTS",
    "PUMP2_COEFFICIENTS",
]
