"""Integration test for the wellheader INSERT loader (end to end)."""
import io

import pandas as pd
from sqlalchemy import text

from app.services import wellheader_loader


def _workbook(df: pd.DataFrame) -> io.BytesIO:
    """Serialize a DataFrame to an in-memory .xlsx with a WELLHEADER sheet."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="WELLHEADER", index=False)
    buf.seek(0)
    return buf


def test_insert_skips_existing_and_isolates_failures(it_schema, monkeypatch):
    engine, schema = it_schema
    with engine.begin() as conn:
        conn.execute(
            text(
                f'CREATE TABLE "{schema}".wellheader '
                "(wellname text, field text, depth numeric NOT NULL)"
            )
        )
        # W1 already exists -> must be skipped, not duplicated.
        conn.execute(text(f"INSERT INTO \"{schema}\".wellheader VALUES ('W1', 'old', 100)"))

    # Point the service at the throwaway schema/engine instead of env config.
    monkeypatch.setattr(wellheader_loader, "load_db_config", lambda company: {"schema": schema})
    monkeypatch.setattr(wellheader_loader, "get_engine", lambda config: engine)

    df = pd.DataFrame(
        {
            "wellname": ["W1", "W2", "W3", "W4"],
            "field": ["a", "b", "c", "d"],
            # W3 has no depth -> NOT NULL violation -> that row fails, others proceed.
            "depth": [10, 20, None, 40],
        }
    )

    result = wellheader_loader.insert_wellheader_from_excel(_workbook(df), "ACME")

    assert "inserted 2 new" in result.message
    assert "skipped 1 existing" in result.message
    assert "1 failed" in result.message

    with engine.connect() as conn:
        rows = conn.execute(
            text(f'SELECT wellname, field, depth FROM "{schema}".wellheader ORDER BY wellname')
        ).fetchall()

    # W1 untouched (old/100), W2 + W4 inserted, W3 skipped due to the failure.
    assert [r[0] for r in rows] == ["W1", "W2", "W4"]
    assert (rows[0][1], int(rows[0][2])) == ("old", 100)
