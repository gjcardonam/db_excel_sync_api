import pytest


@pytest.mark.parametrize("path", ["/", "/well-configuration", "/wellheader"])
def test_ui_pages_render(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_ui_renders_validation_message_for_bad_file(client):
    resp = client.post(
        "/well-configuration/process",
        data={"company": "ACME", "lift_method": "ESP"},
        files={"file": ("bad.txt", b"x", "text/plain")},
    )
    assert resp.status_code == 200
    # The page re-renders with the orange validation block containing the reason.
    assert "File must be a .xlsx file." in resp.text
    assert "was not applied" in resp.text
