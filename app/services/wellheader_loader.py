from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import String, inspect, text

from app.core.config import load_db_config
from app.core.database import get_engine
from app.core.logger import get_logger
from app.utils.excel_reader import read_excel
from app.validation import COPIAFORMATO, ExcelValidationError, Severity, ValidationIssue

logger = get_logger(__name__)

# Show at most this many identifiers in a single warning message.
_MAX_SHOWN = 25

# Columns that mirror the table's auto-assigned index: id == uwi == entityid.
# They are filled by the service for each new well, never taken from the sheet.
_INDEX_COL = "id"
_MIRROR_COLS = ("id", "uwi", "entityid")

# System columns the service fills with a SQL expression when the table has them
# and the sheet does not provide a value. The service is what creates the wells,
# so their creation date is "now". Values are trusted SQL literals (not user input).
_AUTO_FILL_SQL = {
    "well_creation_date": "CURRENT_DATE",
}

# Everything the service supplies on its own, so it is never reported as a
# "missing required column" the user must add to the sheet.
_SERVICE_FILLED = set(_MIRROR_COLS) | set(_AUTO_FILL_SQL)


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


def _wellheader_columns(engine, schema: str, table: str = "wellheader"):
    """Inspect the table and return three views of its columns:

    * ``colmap``   -> {lowercase: real_name}
    * ``coltypes`` -> {lowercase: sqlalchemy_type}
    * ``required`` -> real names of columns that are NOT NULL **and** have no DB
      default. These must be supplied (or assigned by the service), otherwise an
      insert will fail with a not-null violation.
    """
    inspector = inspect(engine)
    cols = inspector.get_columns(table_name=table, schema=schema)
    colmap = {c["name"].lower(): c["name"] for c in cols}
    coltypes = {c["name"].lower(): c["type"] for c in cols}
    required = [c["name"] for c in cols if not c.get("nullable", True) and c.get("default") is None]
    return colmap, coltypes, required


def _mirror_value(coltype, n: int):
    """Cast the index value to match the column type (text columns get a string)."""
    return str(n) if isinstance(coltype, String) else n


def insert_wellheader_from_excel(file, company: str, sheet_name: str = "WELLHEADER") -> WellheaderLoadResult:
    """
    Reads an Excel file and INSERTS new wells into wellheader (as opposed to the
    updater, which updates existing ones). Column headers must match wellheader
    column names.

    The table index is assigned by the service: each new well gets the next
    increasing number (current ``MAX(id) + 1``) and that same value is written to
    ``id``, ``uwi`` and ``entityid`` (whichever of those columns exist), so they
    always match. These three are never taken from the sheet. ``well_creation_date``
    (when present) is set to the current date, since the service is what creates
    the wells. All of these are excluded from the missing-required-column check.

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

    colmap, coltypes, required = _wellheader_columns(engine, schema, table="wellheader")
    insert_cols = [c for c in df.columns if c in colmap]
    if "wellname" not in insert_cols:
        raise ExcelValidationError(
            [ValidationIssue("The wellheader table has no 'wellname' column to insert into.", Severity.ERROR)]
        )

    # Fail fast: list ALL mandatory columns (NOT NULL, no DB default) that the
    # sheet does not provide and the service does not auto-fill, so the user fixes
    # them in one go instead of discovering them one not-null error at a time.
    provided = {c for c in df.columns if c in colmap}
    missing_required = sorted(
        name
        for name in required
        if name.lower() not in provided and name.lower() not in _SERVICE_FILLED
    )
    if missing_required:
        raise ExcelValidationError(
            [
                ValidationIssue(
                    "Your file is missing required column(s) for wellheader: "
                    f"{', '.join(missing_required)}. Add them to the '{sheet_name}' sheet.",
                    Severity.ERROR,
                )
            ]
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

    # The id/uwi/entityid columns mirror the table's increasing index and are
    # assigned by the service, never taken from the sheet.
    mirror_present = [c for c in _MIRROR_COLS if c in colmap]
    index_col = colmap.get(_INDEX_COL) or colmap.get("entityid")
    sheet_cols = [c for c in insert_cols if c not in _MIRROR_COLS]

    inserted = 0
    failed: list[str] = []
    with engine.begin() as conn:
        # Next index value = current max + 1, advanced per inserted row. A failed
        # row simply leaves a gap (ids stay unique and increasing).
        next_id = 0
        if mirror_present and index_col is not None:
            next_id = int(
                conn.execute(
                    text(f'SELECT COALESCE(MAX("{index_col}"), 0) FROM "{schema}"."wellheader"')
                ).scalar()
                or 0
            )

        for _, row in df.iterrows():
            # Only insert provided (non-blank) values for matched columns.
            payload = {}
            for c in sheet_cols:
                val = row.get(c)
                if pd.isna(val):
                    continue
                if isinstance(val, str) and val.strip() == "":
                    continue
                payload[c] = val

            if "wellname" not in payload:
                continue

            cols_sql = [f'"{colmap[c]}"' for c in payload]
            params_sql = [f":{c}" for c in payload]
            binds = dict(payload)

            # Assign the same increasing index to id == uwi == entityid.
            if mirror_present and index_col is not None:
                next_id += 1
                for c in mirror_present:
                    key = f"_idx_{c}"
                    cols_sql.append(f'"{colmap[c]}"')
                    params_sql.append(f":{key}")
                    binds[key] = _mirror_value(coltypes[c], next_id)

            # Fill service-managed system columns (e.g. well_creation_date) with a
            # SQL expression when the table has them and the sheet did not provide one.
            for col, expr in _AUTO_FILL_SQL.items():
                if col in colmap and col not in payload:
                    cols_sql.append(f'"{colmap[col]}"')
                    params_sql.append(expr)

            sql = text(
                f'INSERT INTO "{schema}"."wellheader" ({", ".join(cols_sql)}) '
                f'VALUES ({", ".join(params_sql)})'
            )

            try:
                # SAVEPOINT: a failed row rolls back only itself, the rest proceed.
                with conn.begin_nested():
                    conn.execute(sql, binds)
                inserted += 1
            except Exception as e:  # noqa: BLE001 - report per-row error, keep going
                failed.append(f"{row['wellname']} ({_short_error(e)})")

        # We assign 'id' explicitly, which does not advance its backing sequence.
        # Realign the sequence to the real MAX(id) so future inserts (this tool,
        # the app, or manual ones using the default) continue without collisions.
        if inserted and index_col is not None:
            seq = conn.execute(
                text("SELECT pg_get_serial_sequence(:tbl, :col)"),
                {"tbl": f"{schema}.wellheader", "col": index_col},
            ).scalar()
            if seq:
                conn.execute(
                    text(
                        f'SELECT setval(:seq, (SELECT MAX("{index_col}") FROM "{schema}"."wellheader"))'
                    ),
                    {"seq": seq},
                )

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
