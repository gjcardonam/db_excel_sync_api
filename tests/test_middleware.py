from app.core.settings import settings
from tests.conftest import XLSX_MIME


def test_oversized_request_is_rejected(client, monkeypatch):
    # Shrink the limit so a tiny body trips it.
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 5)
    resp = client.post(
        "/api/v1/wellheader/upload",
        data={"company": "ACME"},
        files={"file": ("wh.xlsx", b"x" * 1000, XLSX_MIME)},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "Request body too large"


def test_normal_request_passes_size_check(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 50 * 1024 * 1024)
    from app.services.wellheader_updater import WellheaderResult

    monkeypatch.setattr(
        "app.api.v1.endpoints.wellheader.update_wellheader_from_excel",
        lambda file, company, sheet: WellheaderResult("ok"),
    )
    resp = client.post(
        "/api/v1/wellheader/upload",
        data={"company": "ACME"},
        files={"file": ("wh.xlsx", b"x" * 1000, XLSX_MIME)},
    )
    assert resp.status_code == 200
