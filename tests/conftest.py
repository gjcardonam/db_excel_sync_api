"""
Shared pytest fixtures.

DB logging and file logging are force-disabled here (before the app is imported)
so the test suite never reaches out to the audit database or writes log files.
"""
import os

# Must be set before importing app.core.settings / app.main.
os.environ["LOG_DB_ENABLED"] = "false"
os.environ["LOG_TO_FILE"] = "false"
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest
from fastapi.testclient import TestClient

from app.main import app

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
