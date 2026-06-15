"""Core abstractions for the data-validation framework.

The design is a simple **rule pattern**: each check is a self-contained
``ValidationRule`` that inspects a DataFrame and returns ``ValidationIssue``
objects. A ``Validator`` runs an ordered list of rules and aggregates the
issues. Adding a new validation later means writing one small rule class and
registering it — nothing else changes.

Issues carry a ``Severity``:
  * ERROR   -> blocks processing (shown RED in the UI).
  * WARNING -> a data problem worth surfacing, does not block (shown ORANGE).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class Severity(StrEnum):
    ERROR = "error"      # hard failure, blocks the upload (RED)
    WARNING = "warning"  # data problem, does not block (ORANGE)


@dataclass(frozen=True)
class ValidationIssue:
    message: str
    severity: Severity = Severity.ERROR
    rule: str = ""


@dataclass
class ValidationContext:
    """Everything a rule may need to know about the upload being validated."""

    company: str
    key_column: str = "well"
    lift_method: str | None = None
    sheet: str | None = None


class ValidationRule(ABC):
    """A single, self-contained validation. Subclass and implement ``validate``."""

    code: str = "rule"

    @abstractmethod
    def validate(self, df: pd.DataFrame, ctx: ValidationContext) -> list[ValidationIssue]:
        ...


class Validator:
    """Runs an ordered list of rules and aggregates their issues."""

    def __init__(self, rules: list[ValidationRule]):
        self._rules = list(rules)

    def validate(self, df: pd.DataFrame, ctx: ValidationContext) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for rule in self._rules:
            issues.extend(rule.validate(df, ctx))
        return issues

    @staticmethod
    def errors(issues: list[ValidationIssue]) -> list[ValidationIssue]:
        return [i for i in issues if i.severity is Severity.ERROR]

    @staticmethod
    def warnings(issues: list[ValidationIssue]) -> list[ValidationIssue]:
        return [i for i in issues if i.severity is Severity.WARNING]


def format_labels(frame: pd.DataFrame, key_column: str, limit: int = 25) -> str:
    """Render a readable, bounded list of well identifiers for a message."""
    if key_column in frame.columns:
        labels = [str(v) for v in frame[key_column].tolist()]
    else:
        labels = [str(i) for i in frame.index.tolist()]
    shown = ", ".join(labels[:limit])
    if len(labels) > limit:
        shown += f", … (+{len(labels) - limit} more)"
    return shown
