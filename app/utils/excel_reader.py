import io
from datetime import datetime

import pandas as pd

from app.core.logger import get_logger

logger = get_logger(__name__)

def to_float_from_excel(v):
    if isinstance(v, datetime):
        return (v - datetime(1899, 12, 30)).total_seconds() / 86400.0
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return float("nan")

# .xlsx files are ZIP archives; a valid one starts with this local-file-header magic.
_XLSX_MAGIC = b"PK\x03\x04"


def read_excel(file, sheet_name, numeric_cols=None):
    f = getattr(file, "file", file)
    if hasattr(f, "seek"):
        f.seek(0)  # rewind the stream to the start

    # Read once to memory (handles SpooledTemporaryFile safely)
    content = f.read() if hasattr(f, "read") else file

    # Validate the real file type, not just the extension: a renamed .xls/.csv
    # or garbage file is rejected up front with a clear message.
    if not isinstance(content, (bytes, bytearray)) or content[:4] != _XLSX_MAGIC:
        raise ValueError("The file is not a valid .xlsx workbook (unexpected file signature).")

    try:
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
        # A bad/corrupt file or a missing sheet is a client error, not a server
        # fault. Raise ValueError so the API layer maps it to HTTP 400.
        logger.exception("Failed to read Excel", extra={"sheet": sheet_name})
        raise ValueError(f"Error reading the Excel file: {e}") from e
