from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import inspect, text

from app.core.config import load_db_config
from app.core.database import get_engine
from app.core.logger import get_logger
from app.utils.excel_reader import read_excel
from app.validation import (
    COPIAFORMATO,
    NUMERIC_COLS,
    ExcelValidationError,
    Severity,
    ValidationContext,
    ValidationIssue,
    Validator,
    data_validator,
    template_validator,
)

logger = get_logger(__name__)


@dataclass
class ProcessResult:
    """Outcome of an upload: a success summary plus any non-blocking warnings."""

    message: str
    warnings: list[str] = field(default_factory=list)


def _drop_copiaformato(df: pd.DataFrame, key_column: str) -> pd.DataFrame:
    return df[df[key_column].astype(str).str.strip().str.upper() != COPIAFORMATO]


def get_table_columns(conn, schema, table):
    inspector = inspect(conn)
    # SQLAlchemy's get_columns(table_name, schema=None)
    cols = inspector.get_columns(table_name=table, schema=schema)
    return [c["name"] for c in cols]


def upsert_table_by_key(conn, df, schema, table, key_col):
    """
    Simple replace-by-key: DELETE ... WHERE key IN (values) + INSERT ALL.
    Runs on the caller-provided connection so it participates in a single
    surrounding transaction.
    """
    if df is None or df.empty:
        return f"{table}: empty DataFrame. Skipped."

    table_cols = get_table_columns(conn, schema, table)
    common = [c for c in df.columns if c in table_cols]
    if not common:
        return f"{table}: no common columns between DataFrame and table. Skipped."

    df_use = df[common].copy()
    if key_col not in df_use.columns:
        return f"{table}: key column '{key_col}' not in DataFrame. Skipped."

    key_vals = df_use[key_col].dropna().unique().tolist()
    if not key_vals:
        return f"{table}: no non-null values for key '{key_col}'. Skipped."

    conn.execute(
        text(f"DELETE FROM {schema}.{table} WHERE {key_col} = ANY(:vals)"),
        {"vals": key_vals},
    )
    # pandas to_sql accepts a SQLAlchemy connection
    df_use.to_sql(table, con=conn, schema=schema, if_exists="append", index=False)

    return f"{table}: replaced {len(df_use)} rows by key '{key_col}'."


def bulk_flag_welltest(conn, df, schema, table="welltest"):
    """
    UPDATE welltest SET process='x' for windows (running, now] per well.
    Runs on the caller-provided connection (single transaction) and issues the
    per-well updates as one batched (executemany) statement.
    """
    if df is None or df.empty or "well" not in df.columns:
        logger.warning("Cannot flag welltest: missing 'well' column or empty DataFrame", extra={"table": table, "schema": schema})
        return f"{table}: missing required 'well' column or empty DataFrame. Skipped."

    # Normalize running
    if "running" not in df.columns:
        if "INSTALL DATE" in df.columns:
            df = df.rename(columns={"INSTALL DATE": "running"})
        else:
            logger.warning("Cannot flag welltest: missing 'running' column", extra={"table": table, "schema": schema})
            return f"{table}: missing 'running' (or 'INSTALL DATE'). Skipped."

    df = df.copy()
    # welltest.time_stamp is `timestamptz`. Use timezone-aware UTC values on BOTH
    # ends of the window so the comparison is unambiguous regardless of the DB
    # session timezone. Naive Excel dates are interpreted as UTC.
    df["running"] = pd.to_datetime(df["running"], errors="coerce", utc=True)
    now_ts = datetime.now(UTC)

    params = [
        {"well": row["well"], "start": row["running"], "end": now_ts}
        for _, row in df.iterrows()
        if not pd.isna(row.get("running")) and not pd.isna(row.get("well"))
    ]
    if not params:
        return f"{table}: no valid (well, running) rows to flag. Skipped."

    conn.execute(
        text(
            f"""
                UPDATE {schema}.{table}
                SET process = 'x'
                WHERE well = :well
                  AND time_stamp > :start
                  AND time_stamp <= :end
            """
        ),
        params,
    )
    return f"{table}: flagged process='x' windows for {len(params)} wells."


def process_excel_and_update_db(file, company, lift_method) -> ProcessResult:
    """
    Processing order:
      1) Validate template integrity (COPIAFORMATO) and data, then remove the
         COPIAFORMATO reference row.
      2) Update main table (dbesp/dbgl).
      3) For GL only, update installrecordgl from 'VALVULAS'.
      4) Finally, flag welltest rows (process='x').

    Raises ExcelValidationError on blocking (ERROR) validations. Non-blocking
    (WARNING) issues are returned in the result so the caller can surface them.
    """
    logger.info("Starting well configuration upload", extra={"company": company, "lift_method": lift_method})
    config = load_db_config(company)
    engine = get_engine(config)
    schema = config["schema"]

    main_sheet = {"ESP": "ESP", "GL": "GAS LIFT"}[lift_method]
    main_table = {"ESP": "dbesp", "GL": "dbgl"}[lift_method]

    df_main = read_excel(file, main_sheet, numeric_cols=NUMERIC_COLS)
    if df_main is None or df_main.empty:
        logger.warning("Main sheet empty or missing", extra={"company": company, "sheet": main_sheet})
        raise ExcelValidationError(
            [ValidationIssue(f"Sheet '{main_sheet}' is empty or not found.", Severity.ERROR)]
        )

    warnings: list[ValidationIssue] = []
    ctx = ValidationContext(company=company, key_column="well", lift_method=lift_method, sheet=main_sheet)

    # 1) Template integrity (COPIAFORMATO must be the first row) on the RAW sheet.
    template_issues = template_validator(ctx).validate(df_main, ctx)
    if Validator.errors(template_issues):
        logger.warning("Template validation failed", extra={"company": company, "sheet": main_sheet})
        raise ExcelValidationError(Validator.errors(template_issues))

    # Now it is safe to drop the reference row.
    df_main = _drop_copiaformato(df_main, "well")
    if df_main.empty:
        raise ExcelValidationError(
            [ValidationIssue(f"Sheet '{main_sheet}' has no data rows besides '{COPIAFORMATO}'.", Severity.ERROR)]
        )

    # 2) Data validation on the cleaned rows.
    data_issues = data_validator(ctx).validate(df_main, ctx)
    if Validator.errors(data_issues):
        logger.warning("Data validation failed", extra={"company": company, "errors": [i.message for i in Validator.errors(data_issues)]})
        raise ExcelValidationError(Validator.errors(data_issues))
    warnings.extend(Validator.warnings(data_issues))

    if lift_method == "ESP":
        df_main["gassepef"] = 90
        df_main["wearfactor1"] = 1

    # For GL, read + validate VALVULAS up-front so all writes share one transaction.
    df_valves = None
    if lift_method == "GL":
        try:
            df_valves = read_excel(file, "VALVULAS")
        except ValueError:
            df_valves = None
            warnings.append(
                ValidationIssue("VALVULAS sheet not found or unreadable; installrecordgl was skipped.", Severity.WARNING)
            )

        if df_valves is not None and not df_valves.empty:
            valves_ctx = ValidationContext(company=company, key_column="wellname", lift_method=lift_method, sheet="VALVULAS")
            valves_issues = template_validator(valves_ctx).validate(df_valves, valves_ctx)
            if Validator.errors(valves_issues):
                raise ExcelValidationError(Validator.errors(valves_issues))
            df_valves = _drop_copiaformato(df_valves, "wellname").copy()
            df_valves["company"] = company

    # All writes share a single transaction: either everything commits or nothing.
    res_install = "installrecordgl: not applicable."
    with engine.begin() as conn:
        res_main = upsert_table_by_key(conn, df_main, schema, main_table, key_col="well")
        logger.info("Main table updated", extra={"company": company, "table": main_table, "result": res_main})

        if lift_method == "GL":
            if df_valves is not None and not df_valves.empty:
                res_install = upsert_table_by_key(conn, df_valves, schema, table="installrecordgl", key_col="wellname")
                logger.info("installrecordgl updated", extra={"company": company, "result": res_install})
            else:
                res_install = "installrecordgl: VALVULAS sheet empty or not found. Skipped."

        res_wt = bulk_flag_welltest(conn, df_main, schema, table="welltest")

    logger.info(
        "Well configuration upload completed",
        extra={"company": company, "lift_method": lift_method, "results": [res_main, res_install, res_wt], "schema": schema},
    )
    return ProcessResult(
        message=" | ".join([res_main, res_install, res_wt]),
        warnings=[w.message for w in warnings],
    )
