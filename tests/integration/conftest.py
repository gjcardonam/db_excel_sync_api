"""
Integration tests run against a real Postgres instance and are skipped unless
IT_DATABASE_URL is set, e.g.:

    IT_DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db python -m pytest tests/integration

Each test gets a throwaway schema that is dropped on teardown, so it never
touches existing data.
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture(scope="session")
def it_database_url():
    url = os.getenv("IT_DATABASE_URL")
    if not url:
        pytest.skip("IT_DATABASE_URL not set; skipping integration tests")
    return url


@pytest.fixture()
def it_schema(it_database_url):
    engine = create_engine(it_database_url)
    schema = "it_" + uuid.uuid4().hex[:12]
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield engine, schema
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
