import pandas as pd
from sqlalchemy import text, inspect

from app.utils.excel_reader import read_excel
from app.core.config import load_db_config
from app.core.database import get_engine
from app.core.logger import get_logger

logger = get_logger(__name__)


def _get_column_map(engine, schema: str, table: str = "wellheader") -> dict:
    """
    Return a dict {lowercase_col: real_col_name} for the given table.
    """
    inspector = inspect(engine)
    cols = inspector.get_columns(table_name=table, schema=schema)
    return {c["name"].lower(): c["name"] for c in cols}


def update_wellheader_from_excel(file, company: str, sheet_name: str = "WELLHEADER") -> str:
    """
    Reads an Excel file, matches columns against wellheader, and performs
    UPDATE per well for the columns provided in the sheet.
    """
    logger.info("Starting wellheader update", extra={"company": company, "sheet": sheet_name})
    config = load_db_config(company)
    engine = get_engine(config)
    schema = config["schema"]

    df = read_excel(file, sheet_name=sheet_name)
    if df is None or df.empty:
        logger.warning("Sheet is empty or missing", extra={"company": company, "sheet": sheet_name})
        raise ValueError("Sheet is empty or does not exist.")

    # Normalize columns to lowercase for matching
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Support legacy column name "well" by renaming to "wellname"
    if "wellname" not in df.columns and "well" in df.columns:
        df = df.rename(columns={"well": "wellname"})

    if "wellname" not in df.columns:
        logger.warning("Missing required column 'wellname'", extra={"company": company, "sheet": sheet_name})
        raise ValueError("Missing required column 'wellname'.")

    # Drop rows without wellname value
    df = df[df["wellname"].notna()]
    if df.empty:
        logger.warning("No rows contain 'wellname' values", extra={"company": company, "sheet": sheet_name})
        raise ValueError("No rows contain a value for 'wellname'.")

    colmap = _get_column_map(engine, schema, table="wellheader")
    well_col = colmap.get("wellname", "wellname")

    update_cols = [c for c in df.columns if c != "wellname" and c in colmap]
    if not update_cols:
        logger.warning("No Excel columns match target table", extra={"company": company, "sheet": sheet_name})
        raise ValueError("No Excel columns match the wellheader table.")

    processed = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            # Build a per-row payload only with provided (non-blank) values
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
            conn.execute(sql, payload)
            processed += 1

    logger.info(
        "Wellheader update completed",
        extra={"company": company, "sheet": sheet_name, "processed_rows": processed, "schema": schema},
    )
    return f"wellheader: processed {processed} rows in schema '{schema}'."
