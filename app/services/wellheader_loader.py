from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import text

from app.core.config import load_db_config
from app.core.database import get_engine
from app.core.logger import get_logger
from app.services.wellheader_updater import _get_column_map
from app.utils.excel_reader import read_excel
from app.validation import COPIAFORMATO, ExcelValidationError, Severity, ValidationIssue

logger = get_logger(__name__)

# Show at most this many identifiers in a single warning message.
_MAX_SHOWN = 25


@dataclass
class WellheaderLoadResult:
    message: str
    warnings: list[str] = field(default_factory=list)


def _shorten(items: list[str]) -> str:
    shown = ", ".join(items[:_MAX_SHOWN])
    if len(items) > _MAX_SHOWN:
        shown += f", … (+{len(items) - _MAX_SHOWN} more)"
    return shown


def _short_error(exc: Exception) -> str:
    """First, human-readable line of a (possibly verbose) DB error."""
    orig = getattr(exc, "orig", exc)
    return str(orig).strip().splitlines()[0]


def insert_wellheader_from_excel(file, company: str, sheet_name: str = "WELLHEADER") -> WellheaderLoadResult:
    """
    Reads an Excel file and INSERTS new wells into wellheader (as opposed to the
    updater, which updates existing ones). Column headers must match wellheader
    column names.

    Error handling (careful by design):
      * Wells whose ``wellname`` already exists are skipped (warning), never
        duplicated.
      * Duplicate ``wellname`` rows inside the file keep the first and warn.
      * Each row is inserted inside its own SAVEPOINT, so a single bad row (e.g.
        a missing NOT NULL value) is reported and skipped without aborting the
        rest. The final message summarizes inserted / skipped / failed counts.

    Raises ExcelValidationError only for blocking, whole-file problems (empty
    sheet, missing 'wellname', no matching columns).
    """
    logger.info("Starting wellheader insert", extra={"company": company, "sheet": sheet_name})
    config = load_db_config(company)
    engine = get_engine(config)
    schema = config["schema"]

    df = read_excel(file, sheet_name=sheet_name)
    if df is None or df.empty:
        raise ExcelValidationError(
            [ValidationIssue(f"Sheet '{sheet_name}' is empty or does not exist.", Severity.ERROR)]
        )

    # Normalize columns to lowercase for matching, support legacy "well".
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "wellname" not in df.columns and "well" in df.columns:
        df = df.rename(columns={"well": "wellname"})

    if "wellname" not in df.columns:
        raise ExcelValidationError(
            [ValidationIssue("Missing required column 'wellname'.", Severity.ERROR)]
        )

    # Drop the COPIAFORMATO reference row if present, then rows without a wellname.
    df = df[df["wellname"].astype(str).str.strip().str.upper() != COPIAFORMATO]
    df = df[df["wellname"].notna()]
    df["wellname"] = df["wellname"].astype(str).str.strip()
    df = df[df["wellname"] != ""]
    if df.empty:
        raise ExcelValidationError(
            [ValidationIssue("No rows contain a value for 'wellname'.", Severity.ERROR)]
        )

    colmap = _get_column_map(engine, schema, table="wellheader")
    insert_cols = [c for c in df.columns if c in colmap]
    if "wellname" not in insert_cols:
        raise ExcelValidationError(
            [ValidationIssue("The wellheader table has no 'wellname' column to insert into.", Severity.ERROR)]
        )

    warnings: list[ValidationIssue] = []

    # Warn about Excel columns ignored because they are not in the table.
    ignored = [c for c in df.columns if c not in colmap]
    if ignored:
        warnings.append(
            ValidationIssue(
                f"These Excel columns were ignored (not in the wellheader table): {', '.join(ignored)}.",
                Severity.WARNING,
            )
        )

    # Drop duplicate wellnames within the file (keep first), warn about them.
    dup_mask = df["wellname"].duplicated(keep="first")
    if dup_mask.any():
        dup_names = sorted(set(df.loc[dup_mask, "wellname"]))
        warnings.append(
            ValidationIssue(
                f"Duplicate 'wellname' rows in the file (only the first was kept): {_shorten(dup_names)}.",
                Severity.WARNING,
            )
        )
        df = df[~dup_mask]

    # Skip wells that already exist in the table.
    names = df["wellname"].tolist()
    with engine.connect() as conn:
        rows = conn.execute(
            text(f'SELECT "{colmap["wellname"]}" FROM "{schema}"."wellheader" WHERE "{colmap["wellname"]}" = ANY(:names)'),
            {"names": names},
        ).fetchall()
    existing = {str(r[0]) for r in rows}
    if existing:
        df = df[~df["wellname"].isin(existing)]
        warnings.append(
            ValidationIssue(
                f"{len(existing)} well(s) already exist in wellheader and were skipped: {_shorten(sorted(existing))}.",
                Severity.WARNING,
            )
        )

    inserted = 0
    failed: list[str] = []
    with engine.begin() as conn:
        for _, row in df.iterrows():
            # Only insert provided (non-blank) values for matched columns.
            payload = {}
            for c in insert_cols:
                val = row.get(c)
                if pd.isna(val):
                    continue
                if isinstance(val, str) and val.strip() == "":
                    continue
                payload[c] = val

            if "wellname" not in payload:
                continue

            cols = list(payload)
            collist = ", ".join(f'"{colmap[c]}"' for c in cols)
            placeholders = ", ".join(f":{c}" for c in cols)
            sql = text(f'INSERT INTO "{schema}"."wellheader" ({collist}) VALUES ({placeholders})')

            try:
                # SAVEPOINT: a failed row rolls back only itself, the rest proceed.
                with conn.begin_nested():
                    conn.execute(sql, payload)
                inserted += 1
            except Exception as e:  # noqa: BLE001 - report per-row error, keep going
                failed.append(f"{row['wellname']} ({_short_error(e)})")

    if failed:
        warnings.append(
            ValidationIssue(
                f"{len(failed)} well(s) could not be inserted: {_shorten(failed)}.",
                Severity.WARNING,
            )
        )

    logger.info(
        "Wellheader insert completed",
        extra={"company": company, "sheet": sheet_name, "inserted": inserted, "skipped_existing": len(existing), "failed": len(failed), "schema": schema},
    )
    return WellheaderLoadResult(
        message=(
            f"wellheader: inserted {inserted} new well(s); "
            f"skipped {len(existing)} existing; {len(failed)} failed. Schema '{schema}'."
        ),
        warnings=[w.message for w in warnings],
    )
