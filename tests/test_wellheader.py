from app.api.v1.endpoints import wellheader
from app.services.wellheader_updater import WellheaderResult
from tests.conftest import XLSX_MIME

URL = "/api/v1/wellheader/upload"


def test_rejects_non_xlsx(client):
    resp = client.post(
        URL,
        data={"company": "ACME"},
        files={"file": ("data.txt", b"x", "text/plain")},
    )
    assert resp.status_code == 400


def test_success(client, monkeypatch):
    monkeypatch.setattr(
        wellheader,
        "update_wellheader_from_excel",
        lambda file, company, sheet: WellheaderResult("processed 5 rows", warnings=["col x ignored"]),
    )
    resp = client.post(
        URL,
        data={"company": "ACME"},
        files={"file": ("wh.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["warnings"] == ["col x ignored"]


def test_validation_error_maps_to_400(client, monkeypatch):
    def _raise(file, company, sheet):
        raise ValueError("missing wellname")

    monkeypatch.setattr(wellheader, "update_wellheader_from_excel", _raise)
    resp = client.post(
        URL,
        data={"company": "ACME"},
        files={"file": ("wh.xlsx", b"x", XLSX_MIME)},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "missing wellname"
