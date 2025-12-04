import io
import pandas as pd
from datetime import datetime
from app.core.logger import get_logger

logger = get_logger(__name__)

def to_float_from_excel(v):
    if isinstance(v, datetime):
        return (v - datetime(1899, 12, 30)).total_seconds() / 86400.0
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return float("nan")

def read_excel(file, sheet_name, numeric_cols=None):
    try:

        f = getattr(file, "file", file)
        if hasattr(f, "seek"):
            f.seek(0)              # rewind the stream to the start

        # Read once to memory (handles SpooledTemporaryFile safely)
        content = f.read() if hasattr(f, "read") else file
        buf = io.BytesIO(content)

        # 1) Quick pass to know real headers
        tmp = pd.read_excel(buf, sheet_name=sheet_name, engine="openpyxl")
        tmp.columns = [c.strip() for c in tmp.columns]

        # 2) Build converters only for present numeric cols
        present = [c for c in (numeric_cols or []) if c in tmp.columns]
        converters = {c: to_float_from_excel for c in present} if present else None

        # Rewind and read applying converters
        buf.seek(0)
        df = pd.read_excel(buf, sheet_name=sheet_name, engine="openpyxl", converters=converters)
        df.columns = [c.strip() for c in df.columns]

        # 3) Force numeric types
        for c in present:
            if pd.api.types.is_datetime64_any_dtype(df[c]):
                df[c] = (df[c] - pd.Timestamp("1899-12-30")) / pd.Timedelta(days=1)
            df[c] = pd.to_numeric(df[c], errors="coerce")

        return df
    except Exception as e:
        logger.exception("Failed to read Excel", extra={"sheet": sheet_name})
        raise RuntimeError(f"Error reading the Excel file: {e}")
