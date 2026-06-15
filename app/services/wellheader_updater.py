from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import inspect, text

from app.core.config import load_db_config
from app.core.database import get_engine
from app.core.logger import get_logger
from app.utils.excel_reader import read_excel
from app.validation import COPIAFORMATO, ExcelValidationError, Severity, ValidationIssue

logger = get_logger(__name__)


@dataclass
class WellheaderResult:
    message: str
    warnings: list[str] = field(default_factory=list)


def _get_column_map(engine, schema: str, table: str = "wellheader") -> dict:
    """Return {lowercase_col: real_col_name} for the given table."""
    inspector = inspect(engine)
    cols = inspector.get_columns(table_name=table, schema=schema)
    return {c["name"].lower(): c["name"] for c in cols}


def update_wellheader_from_excel(file, company: str, sheet_name: str = "WELLHEADER") -> WellheaderResult:
    """
    Reads an Excel file, matches columns against wellheader, and performs an
    UPDATE per well for the columns provided in the sheet.

    Raises ExcelValidationError on blocking problems. Non-blocking problems
    (ignored columns, wells not found in the DB) are returned as warnings.
    """
    logger.info("Starting wellheader update", extra={"company": company, "sheet": sheet_name})
    config = load_db_config(company)
    engine = get_engine(config)
    schema = config["schema"]

    df = read_excel(file, sheet_name=sheet_name)
    if df is None or df.empty:
        raise ExcelValidationError(
            [ValidationIssue(f"Sheet '{sheet_name}' is empty or does not exist.", Severity.ERROR)]
        )

    # Normalize columns to lowercase for matching.
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Support the legacy column name "well" by renaming to "wellname".
    if "wellname" not in df.columns and "well" in df.columns:
        df = df.rename(columns={"well": "wellname"})

    if "wellname" not in df.columns:
        raise ExcelValidationError(
            [ValidationIssue("Missing required column 'wellname'.", Severity.ERROR)]
        )

    # Drop the COPIAFORMATO reference row if present, then rows without a wellname.
    df = df[df["wellname"].astype(str).str.strip().str.upper() != COPIAFORMATO]
    df = df[df["wellname"].notna()]
    if df.empty:
        raise ExcelValidationError(
            [ValidationIssue("No rows contain a value for 'wellname'.", Severity.ERROR)]
        )

    colmap = _get_column_map(engine, schema, table="wellheader")
    well_col = colmap.get("wellname", "wellname")

    update_cols = [c for c in df.columns if c != "wellname" and c in colmap]
    if not update_cols:
        raise ExcelValidationError(
            [ValidationIssue("No Excel columns match the wellheader table.", Severity.ERROR)]
        )

    warnings: list[ValidationIssue] = []

    # Warn about Excel columns that were ignored because they don't exist in the table.
    ignored = [c for c in df.columns if c != "wellname" and c not in colmap]
    if ignored:
        warnings.append(
            ValidationIssue(
                f"These Excel columns were ignored (not in the wellheader table): {', '.join(ignored)}.",
                Severity.WARNING,
            )
        )

    processed = 0
    not_found: list[str] = []
    with engine.begin() as conn:
        for _, row in df.iterrows():
            # Build a per-row payload only with provided (non-blank) values.
            row_values = {}
            for c in update_cols:
                val = row.get(c)
                if pd.isna(val):
                    continue
                if isinstance(val, str) and val.strip() == "":
                    continue
                row_values[c] = val

            if not row_values:
                continue

            set_clause = ", ".join([f'"{colmap[c]}" = :{c}' for c in row_values])
            sql = text(
                f'UPDATE "{schema}"."wellheader" '
                f"SET {set_clause} "
                f'WHERE "{well_col}" = :well_value'
            )

            payload = {c: row_values[c] for c in row_values}
            payload["well_value"] = row["wellname"]
            result = conn.execute(sql, payload)
            if result.rowcount and result.rowcount > 0:
                processed += 1
            else:
                not_found.append(str(row["wellname"]))

    # Warn about wells that were not found in the table (the UPDATE matched no rows).
    if not_found:
        shown = ", ".join(not_found[:25])
        if len(not_found) > 25:
            shown += f", … (+{len(not_found) - 25} more)"
        warnings.append(
            ValidationIssue(f"{len(not_found)} well(s) not found in wellheader and skipped: {shown}.", Severity.WARNING)
        )

    logger.info(
        "Wellheader update completed",
        extra={"company": company, "sheet": sheet_name, "processed_rows": processed, "not_found": len(not_found), "schema": schema},
    )
    return WellheaderResult(
        message=f"wellheader: updated {processed} well(s) in schema '{schema}'.",
        warnings=[w.message for w in warnings],
    )
