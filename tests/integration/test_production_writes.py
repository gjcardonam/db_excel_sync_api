"""Integration tests for the Postgres-specific SQL in production_processor."""
from datetime import date

import pandas as pd
from sqlalchemy import text

from app.services.production_processor import (
    _lookup_entityids,
    upsert_table_by_keys,
)


def test_upsert_by_keys_replaces_rows_by_composite_key(it_schema):
    engine, schema = it_schema
    with engine.begin() as conn:
        conn.execute(
            text(
                f'CREATE TABLE "{schema}".sumdailyproduction '
                "(entityid int, docdate date, oil numeric, gas numeric, water numeric)"
            )
        )
        # Existing row for (1, 2026-01-01) should be overwritten; (1, 2026-01-02) untouched.
        conn.execute(
            text(
                f'INSERT INTO "{schema}".sumdailyproduction VALUES '
                "(1, DATE '2026-01-01', 5, 5, 5),"
                "(1, DATE '2026-01-02', 7, 7, 7)"
            )
        )

    df = pd.DataFrame(
        {
            "entityid": [1, 2],
            "docdate": [date(2026, 1, 1), date(2026, 1, 1)],
            "oil": [100, 200],
            "gas": [10, 20],
            "water": [1, 2],
        }
    )
    with engine.begin() as conn:
        msg = upsert_table_by_keys(conn, df, schema, "sumdailyproduction", ["entityid", "docdate"])

    assert "replaced 2 rows" in msg
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f'SELECT entityid, docdate, oil FROM "{schema}".sumdailyproduction '
                "ORDER BY entityid, docdate"
            )
        ).fetchall()

    # (1, 01-01) overwritten to 100, (1, 01-02) preserved, (2, 01-01) inserted.
    assert [tuple(r) for r in rows] == [
        (1, date(2026, 1, 1), 100),
        (1, date(2026, 1, 2), 7),
        (2, date(2026, 1, 1), 200),
    ]


def test_upsert_by_keys_only_writes_common_columns(it_schema):
    engine, schema = it_schema
    with engine.begin() as conn:
        conn.execute(
            text(
                f'CREATE TABLE "{schema}".docwellheadpressures '
                "(productionptid int, docdate date, tubingpressure numeric, casingpressure numeric)"
            )
        )

    # 'entityid' is not a column here and must be ignored.
    df = pd.DataFrame(
        {
            "productionptid": [1],
            "docdate": [date(2026, 3, 1)],
            "tubingpressure": [50],
            "casingpressure": [60],
            "entityid": [999],
        }
    )
    with engine.begin() as conn:
        upsert_table_by_keys(conn, df, schema, "docwellheadpressures", ["productionptid", "docdate"])

    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"SELECT productionptid, tubingpressure, casingpressure "
                f'FROM "{schema}".docwellheadpressures'
            )
        ).fetchone()
    assert tuple(row) == (1, 50, 60)


def test_lookup_entityids_maps_wellname_to_entityid(it_schema):
    engine, schema = it_schema
    with engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "{schema}".wellheader (wellname text, entityid int)'))
        conn.execute(
            text(
                f'INSERT INTO "{schema}".wellheader VALUES '
                "('W1', 11), ('W2', 22), ('NOID', NULL)"
            )
        )

    with engine.connect() as conn:
        mapping = _lookup_entityids(conn, schema, ["W1", "W2", "NOID", "MISSING"])

    # NULL entityid and missing wells are excluded.
    assert mapping == {"W1": 11, "W2": 22}
