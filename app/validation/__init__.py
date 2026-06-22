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
    PRODUCTION_NUMERIC_COLS,
    PRODUCTION_REQUIRED_COLUMNS,
    PUMP2_COEFFICIENTS,
    REQUIRED_PUMP_COEFFICIENTS,
)
from app.validation.exceptions import ExcelValidationError
from app.validation.registry import (
    data_validator,
    production_data_validator,
    production_template_validator,
    template_validator,
)

__all__ = [
    "Severity",
    "ValidationContext",
    "ValidationIssue",
    "ValidationRule",
    "Validator",
    "ExcelValidationError",
    "data_validator",
    "template_validator",
    "production_data_validator",
    "production_template_validator",
    "COPIAFORMATO",
    "NUMERIC_COLS",
    "PRODUCTION_NUMERIC_COLS",
    "PRODUCTION_REQUIRED_COLUMNS",
    "REQUIRED_PUMP_COEFFICIENTS",
    "PUMP2_COEFFICIENTS",
]
