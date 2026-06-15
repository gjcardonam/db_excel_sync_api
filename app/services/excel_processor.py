from datetime import datetime

import pandas as pd
from sqlalchemy import text, inspect

from app.utils.excel_reader import read_excel
from app.core.config import load_db_config
from app.core.database import get_engine
from app.core.logger import get_logger

NUMERIC_COLS = [
    "x5", "x4", "x3", "x2", "x1", "x0",
    "x51", "x41", "x31", "x21", "x11", "x01",
    "x52x", "x42x", "x32x", "x22x", "x12x", "x02x",
    "x53x", "x43x", "x33x", "x23x", "x13x", "x03x",
]

REQUIRED_PUMP_COEFFICIENTS = [
    "x5", "x4", "x3", "x2", "x1", "x0",
    "x51", "x41", "x31", "x21", "x11", "x01",
]

PUMP2_COEFFICIENTS = [
    "x52x", "x42x", "x32x", "x22x", "x12x", "x02x",
    "x53x", "x43x", "x33x", "x23x", "x13x", "x03x",
]

logger = get_logger(__name__)


def validate_pump_coefficients(df):
    """
    Validates that all wells have the required pump coefficient values and time_stamp.
    - All wells must have: x5, x4, x3, x2, x1, x0, x51, x41, x31, x21, x11, x01
    - If a well has 'pump2', it must also have: x52x, x42x, x32x, x22x, x12x, x02x,
      x53x, x43x, x33x, x23x, x13x, x03x
    - time_stamp is always required
    """
    errors = []

    if "time_stamp" not in df.columns:
        errors.append("Missing required column 'time_stamp'.")
    else:
        missing_ts = df[df["time_stamp"].isna()]
        if not missing_ts.empty:
            wells = missing_ts["well"].tolist() if "well" in df.columns else missing_ts.index.tolist()
            errors.append(f"Wells missing 'time_stamp': {wells}")

    for col in REQUIRED_PUMP_COEFFICIENTS:
        if col not in df.columns:
            errors.append(f"Missing required column '{col}'.")
            continue
        missing = df[df[col].isna()]
        if not missing.empty:
            wells = missing["well"].tolist() if "well" in df.columns else missing.index.tolist()
            errors.append(f"Wells missing '{col}': {wells}")

    has_pump2 = "pump2" in df.columns and df["pump2"].notna().any()
    if has_pump2:
        for col in PUMP2_COEFFICIENTS:
            if col not in df.columns:
                errors.append(f"Missing required column '{col}' (required when pump2 is present).")
                continue
            wells_with_pump2 = df[df["pump2"].notna()]
            missing = wells_with_pump2[wells_with_pump2[col].isna()]
            if not missing.empty:
                wells = missing["well"].tolist() if "well" in df.columns else missing.index.tolist()
                errors.append(f"Wells with pump2 missing '{col}': {wells}")

    return errors


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
    df["running"] = pd.to_datetime(df["running"], errors="coerce")
    now_ts = datetime.now()

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


def process_excel_and_update_db(file, company, lift_method):
    """
    Processing order:
      1) Update main table (dbesp/dbgl)
      2) For GL only, update installrecordgl from 'VALVULAS'
      3) Finally, flag welltest rows (process='x')
    """
    logger.info("Starting well configuration upload", extra={"company": company, "lift_method": lift_method})
    config = load_db_config(company)
    engine = get_engine(config)
    schema = config["schema"]

    # Main sheet / table
    main_sheet = {"ESP": "ESP", "GL": "GAS LIFT"}[lift_method]
    main_table = {"ESP": "dbesp", "GL": "dbgl"}[lift_method]

    df_main = read_excel(file, main_sheet, numeric_cols=NUMERIC_COLS)
    if df_main is None or df_main.empty:
        logger.warning("Main sheet empty or missing", extra={"company": company, "sheet": main_sheet})
        return "Main sheet empty or not found."

    if "well" in df_main.columns:
        df_main = df_main[df_main["well"] != "COPIAFORMATO"]

    if lift_method == "ESP":
        validation_errors = validate_pump_coefficients(df_main)
        if validation_errors:
            error_msg = "Validation failed: " + "; ".join(validation_errors)
            logger.warning("Pump coefficient validation failed", extra={"company": company, "errors": validation_errors})
            raise ValueError(error_msg)

    if lift_method == "ESP":
        df_main["gassepef"] = 90
        df_main["wearfactor1"] = 1

    # If GL, read the VALVULAS sheet up-front so all writes happen in one transaction.
    df_valves = None
    if lift_method == "GL":
        df_valves = read_excel(file, "VALVULAS")
        if df_valves is not None and not df_valves.empty:
            if "wellname" in df_valves.columns:
                df_valves = df_valves[df_valves["wellname"] != "COPIAFORMATO"]
            df_valves = df_valves.copy()
            df_valves["company"] = company

    # All three writes share a single transaction: either everything commits or
    # nothing does, so a mid-way failure can't leave the schema inconsistent.
    res_install = "installrecordgl: not applicable."
    with engine.begin() as conn:
        # 1) Update main table
        res_main = upsert_table_by_key(conn, df_main, schema, main_table, key_col="well")
        logger.info("Main table updated", extra={"company": company, "table": main_table, "result": res_main})

        # 2) If GL, update installrecordgl before touching welltest
        if lift_method == "GL":
            if df_valves is not None and not df_valves.empty:
                res_install = upsert_table_by_key(
                    conn, df_valves, schema, table="installrecordgl", key_col="wellname"
                )
                logger.info(
                    "installrecordgl updated",
                    extra={"company": company, "table": "installrecordgl", "result": res_install},
                )
            else:
                res_install = "installrecordgl: VALVULAS sheet empty or not found. Skipped."
                logger.warning("VALVULAS sheet empty or missing", extra={"company": company, "sheet": "VALVULAS"})

        # 3) Only at the end: update welltest
        res_wt = bulk_flag_welltest(conn, df_main, schema, table="welltest")

    logger.info(
        "Well configuration upload completed",
        extra={
            "company": company,
            "lift_method": lift_method,
            "results": [res_main, res_install, res_wt],
            "schema": schema,
        },
    )
    return " | ".join([res_main, res_install, res_wt])
