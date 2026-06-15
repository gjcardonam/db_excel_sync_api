from app.api.v1.endpoints import upload
from app.services.excel_processor import ProcessResult
from tests.conftest import XLSX_MIME

URL = "/api/v1/well-configuration/"


def test_rejects_non_xlsx(client):
    resp = client.post(
        URL,
        data={"company": "ACME", "lift_method": "ESP"},
        files={"file": ("data.txt", b"x", "text/plain")},
    )
    assert resp.status_code == 400


def test_missing_fields(client):
    resp = client.post(URL, data={"company": "ACME"})
    assert resp.status_code == 400


def test_invalid_lift_method(client):
    resp = client.post(
        URL,
        data={"company": "ACME", "lift_method": "ROD"},
        files={"file": ("wells.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 400


def test_success(client, monkeypatch):
    monkeypatch.setattr(
        upload,
        "process_excel_and_update_db",
        lambda file, company, lift: ProcessResult("3 rows", warnings=["dup W1"]),
    )
    resp = client.post(
        URL,
        data={"company": "ACME", "lift_method": "esp"},
        files={"file": ("wells.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["message"] == "3 rows"
    assert body["warnings"] == ["dup W1"]


def test_validation_error_lists_issues(client, monkeypatch):
    from app.validation import ExcelValidationError, Severity, ValidationIssue

    def _raise(file, company, lift):
        raise ExcelValidationError(
            [ValidationIssue("COPIAFORMATO row missing.", Severity.ERROR)]
        )

    monkeypatch.setattr(upload, "process_excel_and_update_db", _raise)
    resp = client.post(
        URL,
        data={"company": "ACME", "lift_method": "ESP"},
        files={"file": ("wells.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == ["COPIAFORMATO row missing."]


def test_validation_error_maps_to_400(client, monkeypatch):
    def _raise(file, company, lift):
        raise ValueError("bad coefficients")

    monkeypatch.setattr(upload, "process_excel_and_update_db", _raise)
    resp = client.post(
        URL,
        data={"company": "ACME", "lift_method": "ESP"},
        files={"file": ("wells.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "bad coefficients"


def test_unexpected_error_maps_to_500(client, monkeypatch):
    def _raise(file, company, lift):
        raise RuntimeError("db down")

    monkeypatch.setattr(upload, "process_excel_and_update_db", _raise)
    resp = client.post(
        URL,
        data={"company": "ACME", "lift_method": "ESP"},
        files={"file": ("wells.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 500
