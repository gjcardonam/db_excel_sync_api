from app.api.v1.endpoints import wellheader_insert
from app.services.wellheader_loader import WellheaderLoadResult
from app.validation import ExcelValidationError, Severity, ValidationIssue
from tests.conftest import XLSX_MIME

URL = "/api/v1/wellheader/insert"


def test_rejects_non_xlsx(client):
    resp = client.post(
        URL,
        data={"company": "ACME"},
        files={"file": ("data.txt", b"x", "text/plain")},
    )
    assert resp.status_code == 400


def test_success(client, monkeypatch):
    monkeypatch.setattr(
        wellheader_insert,
        "insert_wellheader_from_excel",
        lambda file, company, sheet: WellheaderLoadResult(
            "wellheader: inserted 3 new well(s); skipped 1 existing; 0 failed.",
            warnings=["1 well(s) already exist in wellheader and were skipped: W1."],
        ),
    )
    resp = client.post(
        URL,
        data={"company": "ACME"},
        files={"file": ("wh.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert "inserted 3 new" in body["message"]
    assert body["warnings"]


def test_validation_error_maps_to_400(client, monkeypatch):
    def _raise(file, company, sheet):
        raise ExcelValidationError([ValidationIssue("Missing required column 'wellname'.", Severity.ERROR)])

    monkeypatch.setattr(wellheader_insert, "insert_wellheader_from_excel", _raise)
    resp = client.post(
        URL,
        data={"company": "ACME"},
        files={"file": ("wh.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == ["Missing required column 'wellname'."]


def test_value_error_maps_to_400(client, monkeypatch):
    def _raise(file, company, sheet):
        raise ValueError("Sheet 'WELLHEADER' is empty or does not exist.")

    monkeypatch.setattr(wellheader_insert, "insert_wellheader_from_excel", _raise)
    resp = client.post(
        URL,
        data={"company": "ACME"},
        files={"file": ("wh.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Sheet 'WELLHEADER' is empty or does not exist."
