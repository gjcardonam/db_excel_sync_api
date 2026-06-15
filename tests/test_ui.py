import pytest


@pytest.mark.parametrize("path", ["/", "/well-configuration", "/wellheader"])
def test_ui_pages_render(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
