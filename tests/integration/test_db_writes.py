"""Integration tests for the Postgres-specific SQL in excel_processor."""
from datetime import UTC, datetime, timedelta

import pandas as pd
from sqlalchemy import text

from app.services.excel_processor import bulk_flag_welltest, upsert_table_by_key


def test_upsert_replaces_rows_by_key(it_schema):
    engine, schema = it_schema
    with engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "{schema}".dbesp (well text, gassepef int)'))
        conn.execute(text(f"INSERT INTO \"{schema}\".dbesp VALUES ('W1', 1), ('OLD', 99)"))

    df = pd.DataFrame({"well": ["W1", "W2"], "gassepef": [90, 90]})
    with engine.begin() as conn:
        msg = upsert_table_by_key(conn, df, schema, "dbesp", "well")

    assert "replaced 2 rows" in msg
    with engine.connect() as conn:
        rows = conn.execute(
            text(f'SELECT well, gassepef FROM "{schema}".dbesp ORDER BY well')
        ).fetchall()

    # W1 replaced, W2 inserted, OLD (not in the upload) left untouched.
    assert [tuple(r) for r in rows] == [("OLD", 99), ("W1", 90), ("W2", 90)]


def test_upsert_only_writes_common_columns(it_schema):
    engine, schema = it_schema
    with engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "{schema}".dbesp (well text, gassepef int)'))

    # 'extra' is not a column in the table and must be ignored.
    df = pd.DataFrame({"well": ["W1"], "gassepef": [90], "extra": ["ignored"]})
    with engine.begin() as conn:
        upsert_table_by_key(conn, df, schema, "dbesp", "well")

    with engine.connect() as conn:
        row = conn.execute(text(f'SELECT well, gassepef FROM "{schema}".dbesp')).fetchone()
    assert tuple(row) == ("W1", 90)


def test_bulk_flag_welltest_flags_only_rows_in_window(it_schema):
    engine, schema = it_schema
    with engine.begin() as conn:
        conn.execute(
            text(
                f'CREATE TABLE "{schema}".welltest '
                "(well text, time_stamp timestamptz, process text)"
            )
        )
        conn.execute(
            text(
                f"INSERT INTO \"{schema}\".welltest VALUES "
                "('W1', now() - interval '1 day', NULL),"   # inside (running, now]
                "('W1', now() - interval '30 day', NULL),"  # before running
                "('W2', now() - interval '1 day', NULL)"    # different well
            )
        )

    running = datetime.now(UTC) - timedelta(days=10)
    df = pd.DataFrame({"well": ["W1"], "running": [running]})
    with engine.begin() as conn:
        bulk_flag_welltest(conn, df, schema, "welltest")

    with engine.connect() as conn:
        flagged = conn.execute(
            text(f"SELECT well, time_stamp FROM \"{schema}\".welltest WHERE process = 'x'")
        ).fetchall()

    # Only W1's recent row falls in the window.
    assert len(flagged) == 1
    assert flagged[0][0] == "W1"
