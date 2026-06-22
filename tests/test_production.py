from app.api.v1.endpoints import production
from app.services.production_processor import ProductionResult
from app.validation import ExcelValidationError, Severity, ValidationIssue
from tests.conftest import XLSX_MIME

URL = "/api/v1/production/upload"


def test_rejects_non_xlsx(client):
    resp = client.post(
        URL,
        data={"company": "ACME"},
        files={"file": ("data.txt", b"x", "text/plain")},
    )
    assert resp.status_code == 400


def test_success(client, monkeypatch):
    monkeypatch.setattr(
        production,
        "process_production_and_update_db",
        lambda file, company: ProductionResult("sumdailyproduction: replaced 3 rows", warnings=["W9 not found"]),
    )
    resp = client.post(
        URL,
        data={"company": "ACME"},
        files={"file": ("prod.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["warnings"] == ["W9 not found"]


def test_validation_error_maps_to_400(client, monkeypatch):
    def _raise(file, company):
        raise ExcelValidationError([ValidationIssue("Missing required column 'oil'.", Severity.ERROR)])

    monkeypatch.setattr(production, "process_production_and_update_db", _raise)
    resp = client.post(
        URL,
        data={"company": "ACME"},
        files={"file": ("prod.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == ["Missing required column 'oil'."]


def test_value_error_maps_to_400(client, monkeypatch):
    def _raise(file, company):
        raise ValueError("Sheet 'PRODUCCION' is empty or not found.")

    monkeypatch.setattr(production, "process_production_and_update_db", _raise)
    resp = client.post(
        URL,
        data={"company": "ACME"},
        files={"file": ("prod.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Sheet 'PRODUCCION' is empty or not found."
