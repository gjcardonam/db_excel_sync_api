from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import text

from app.core.config import load_db_config
from app.core.database import get_engine
from app.core.logger import get_logger
from app.services.excel_processor import _drop_copiaformato, get_table_columns
from app.utils.excel_reader import read_excel
from app.validation import (
    COPIAFORMATO,
    PRODUCTION_NUMERIC_COLS,
    ExcelValidationError,
    Severity,
    ValidationContext,
    ValidationIssue,
    Validator,
    production_data_validator,
    production_template_validator,
)

logger = get_logger(__name__)

SHEET_NAME = "PRODUCCION"
KEY_COLUMN = "wellname"

# Routing of production measurements by the 'origin' value (exact, case-sensitive).
ORIGIN_ALLOCATED = "allocated"
ORIGIN_TEST = "test"

# Measurement columns that go to the production tables (sumdailyproduction / docwelltests).
PRODUCTION_VALUE_COLS = ["oil", "gas", "water"]
# Measurement columns that always go to docwellheadpressures.
PRESSURE_VALUE_COLS = ["tubingpressure", "casingpressure"]


@dataclass
class ProductionResult:
    """Outcome of a production upload: a success summary plus non-blocking warnings."""

    message: str
    warnings: list[str] = field(default_factory=list)


def upsert_table_by_keys(conn, df, schema, table, key_cols):
    """
    Composite-key replace: DELETE rows matching each (key_cols) tuple present in
    ``df`` then INSERT all rows. Runs on the caller-provided connection so it
    participates in a single surrounding transaction.
    """
    if df is None or df.empty:
        return f"{table}: empty DataFrame. Skipped."

    table_cols = get_table_columns(conn, schema, table)
    common = [c for c in df.columns if c in table_cols]
    if not common:
        return f"{table}: no common columns between DataFrame and table. Skipped."

    missing_keys = [k for k in key_cols if k not in common]
    if missing_keys:
        return f"{table}: key column(s) {missing_keys} not in table/DataFrame. Skipped."

    df_use = df[common].copy()
    # Drop rows missing any key value (cannot be uniquely keyed).
    df_use = df_use.dropna(subset=key_cols)
    if df_use.empty:
        return f"{table}: no rows with complete keys {key_cols}. Skipped."

    # Keep one row per key tuple (the last wins), so the INSERT cannot create
    # duplicates for the same (well, date).
    df_use = df_use.drop_duplicates(subset=key_cols, keep="last")

    where = " AND ".join(f"{k} = :{k}" for k in key_cols)
    params = [
        {k: row[k] for k in key_cols}
        for _, row in df_use.iterrows()
    ]
    conn.execute(text(f"DELETE FROM {schema}.{table} WHERE {where}"), params)

    # pandas to_sql accepts a SQLAlchemy connection.
    df_use.to_sql(table, con=conn, schema=schema, if_exists="append", index=False)

    return f"{table}: replaced {len(df_use)} rows by keys {key_cols}."


def _lookup_entityids(conn, schema, wellnames) -> dict:
    """Return {wellname: entityid} from {schema}.wellheader for the given names."""
    names = [str(w) for w in wellnames if pd.notna(w)]
    if not names:
        return {}
    rows = conn.execute(
        text(
            f"SELECT wellname, entityid FROM {schema}.wellheader "
            f"WHERE wellname = ANY(:names)"
        ),
        {"names": names},
    ).fetchall()
    return {r[0]: r[1] for r in rows if r[1] is not None}


def process_production_and_update_db(file, company) -> ProductionResult:
    """
    Read the PRODUCCION sheet and route daily production/pressure data into the
    company schema:

      * origin == 'allocated' -> sumdailyproduction (docdate, oil, gas, water, entityid)
      * origin == 'test'      -> docwelltests      (docdate, oil, gas, water, entityid)
      * tubingpressure/casingpressure -> docwellheadpressures
        (docdate, tubingpressure, casingpressure, productionptid) for ALL rows.

    Records are unique per well + day: an incoming (entityid, docdate) overwrites
    an existing row, otherwise it is inserted. All writes share one transaction.

    Raises ExcelValidationError on blocking problems. Non-blocking issues (wells
    not found, unparseable dates, unknown origin) are returned as warnings.
    """
    logger.info("Starting production upload", extra={"company": company, "sheet": SHEET_NAME})
    config = load_db_config(company)
    engine = get_engine(config)
    schema = config["schema"]

    df = read_excel(file, SHEET_NAME, numeric_cols=PRODUCTION_NUMERIC_COLS)
    if df is None or df.empty:
        raise ExcelValidationError(
            [ValidationIssue(f"Sheet '{SHEET_NAME}' is empty or not found.", Severity.ERROR)]
        )

    warnings: list[ValidationIssue] = []
    ctx = ValidationContext(company=company, key_column=KEY_COLUMN, sheet=SHEET_NAME)

    # 1) Template integrity (COPIAFORMATO must be the first row) on the RAW sheet.
    template_issues = production_template_validator(ctx).validate(df, ctx)
    if Validator.errors(template_issues):
        logger.warning("Production template validation failed", extra={"company": company})
        raise ExcelValidationError(Validator.errors(template_issues))

    # Now it is safe to drop the reference row.
    df = _drop_copiaformato(df, KEY_COLUMN).copy()
    if df.empty:
        raise ExcelValidationError(
            [ValidationIssue(f"Sheet '{SHEET_NAME}' has no data rows besides '{COPIAFORMATO}'.", Severity.ERROR)]
        )

    # 2) Data validation (required columns present) on the cleaned rows.
    data_issues = production_data_validator(ctx).validate(df, ctx)
    if Validator.errors(data_issues):
        logger.warning("Production data validation failed", extra={"company": company, "errors": [i.message for i in Validator.errors(data_issues)]})
        raise ExcelValidationError(Validator.errors(data_issues))
    warnings.extend(Validator.warnings(data_issues))

    # 3) Normalize docdate to a python date (day-level uniqueness; matches a `date`
    #    column and works against `timestamp` too). Drop rows we cannot key by date.
    df["docdate"] = pd.to_datetime(df["docdate"], errors="coerce").dt.date
    bad_dates = df[df["docdate"].isna()]
    if not bad_dates.empty:
        names = ", ".join(str(w) for w in bad_dates[KEY_COLUMN].tolist()[:25])
        warnings.append(
            ValidationIssue(
                f"{len(bad_dates)} row(s) have an unreadable 'docdate' and were skipped: {names}.",
                Severity.WARNING,
            )
        )
        df = df[df["docdate"].notna()].copy()

    if df.empty:
        raise ExcelValidationError(
            [ValidationIssue("No rows with a valid 'docdate' to process.", Severity.ERROR)]
        )

    # 4) Resolve entityid for each well from wellheader. Rows with no match cannot
    #    be written (no id) and are skipped with a warning.
    with engine.connect() as conn:
        name_to_id = _lookup_entityids(conn, schema, df[KEY_COLUMN].unique().tolist())

    df["entityid"] = df[KEY_COLUMN].map(name_to_id)
    not_found = df[df["entityid"].isna()]
    if not not_found.empty:
        missing_names = sorted({str(w) for w in not_found[KEY_COLUMN].tolist()})
        shown = ", ".join(missing_names[:25])
        if len(missing_names) > 25:
            shown += f", … (+{len(missing_names) - 25} more)"
        warnings.append(
            ValidationIssue(
                f"{len(missing_names)} well(s) not found in wellheader and skipped: {shown}.",
                Severity.WARNING,
            )
        )
        df = df[df["entityid"].notna()].copy()

    if df.empty:
        raise ExcelValidationError(
            [ValidationIssue("No rows matched a well in wellheader; nothing to write.", Severity.ERROR)]
        )

    # 5) Warn about rows whose origin is neither 'allocated' nor 'test' (production
    #    skipped for them; their pressures are still written).
    known_origin = df["origin"].isin([ORIGIN_ALLOCATED, ORIGIN_TEST])
    unknown = df[~known_origin]
    if not unknown.empty:
        names = ", ".join(str(w) for w in unknown[KEY_COLUMN].tolist()[:25])
        warnings.append(
            ValidationIssue(
                f"{len(unknown)} row(s) have an unrecognized 'origin' (expected "
                f"'{ORIGIN_ALLOCATED}' or '{ORIGIN_TEST}'); production was skipped "
                f"(pressures still saved): {names}.",
                Severity.WARNING,
            )
        )

    # 6) Build the destination frames.
    prod_cols = ["entityid", "docdate", *PRODUCTION_VALUE_COLS]
    sum_df = df[df["origin"] == ORIGIN_ALLOCATED][prod_cols].copy()
    wt_df = df[df["origin"] == ORIGIN_TEST][prod_cols].copy()

    press_df = df[["entityid", "docdate", *PRESSURE_VALUE_COLS]].copy()
    press_df = press_df.rename(columns={"entityid": "productionptid"})
    # Skip rows where both pressures are empty (nothing to record).
    press_df = press_df.dropna(subset=PRESSURE_VALUE_COLS, how="all")

    # 7) All writes share a single transaction: everything commits or nothing.
    with engine.begin() as conn:
        res_sum = upsert_table_by_keys(conn, sum_df, schema, "sumdailyproduction", ["entityid", "docdate"])
        res_wt = upsert_table_by_keys(conn, wt_df, schema, "docwelltests", ["entityid", "docdate"])
        res_p = upsert_table_by_keys(conn, press_df, schema, "docwellheadpressures", ["productionptid", "docdate"])

    logger.info(
        "Production upload completed",
        extra={"company": company, "results": [res_sum, res_wt, res_p], "schema": schema},
    )
    return ProductionResult(
        message=" | ".join([res_sum, res_wt, res_p]),
        warnings=[w.message for w in warnings],
    )
