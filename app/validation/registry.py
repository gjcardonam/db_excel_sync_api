"""Registry that builds the right set of rules for a given upload.

This is the single place to wire validations. To add validations later
(e.g. GL-specific rules), extend the lists here — services do not change.
"""
from __future__ import annotations

from app.validation.base import ValidationContext, Validator
from app.validation.constants import (
    PRODUCTION_REQUIRED_COLUMNS,
    PUMP2_COEFFICIENTS,
    REQUIRED_PUMP_COEFFICIENTS,
)
from app.validation.rules import (
    CopiaFormatoPresentRule,
    DuplicateKeysRule,
    NonNullValuesRule,
    Pump2CoefficientsRule,
    RequiredColumnsRule,
    TimestampRequiredRule,
)


def template_validator(ctx: ValidationContext) -> Validator:
    """Rules that run on the RAW sheet, before the COPIAFORMATO row is removed."""
    return Validator([CopiaFormatoPresentRule()])


def data_validator(ctx: ValidationContext) -> Validator:
    """Rules that run on the cleaned data (COPIAFORMATO already removed)."""
    rules = [DuplicateKeysRule()]

    if ctx.lift_method == "ESP":
        rules += [
            TimestampRequiredRule(),
            RequiredColumnsRule(REQUIRED_PUMP_COEFFICIENTS),
            NonNullValuesRule(REQUIRED_PUMP_COEFFICIENTS),
            Pump2CoefficientsRule(PUMP2_COEFFICIENTS),
        ]
    # GL: data rules to be defined later — only the common rules apply for now.

    return Validator(rules)


def production_template_validator(ctx: ValidationContext) -> Validator:
    """Rules for the PRODUCCION sheet, run before the COPIAFORMATO row is removed."""
    return Validator([CopiaFormatoPresentRule()])


def production_data_validator(ctx: ValidationContext) -> Validator:
    """Rules for the cleaned PRODUCCION data (COPIAFORMATO already removed)."""
    return Validator([RequiredColumnsRule(PRODUCTION_REQUIRED_COLUMNS)])
