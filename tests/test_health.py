from app.api.v1.endpoints import health


def test_liveness(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ping_db_success(client, monkeypatch):
    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, *args, **kwargs):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    monkeypatch.setattr(health, "load_db_config", lambda company: {"schema": "s"})
    monkeypatch.setattr(health, "get_engine", lambda config: _FakeEngine())

    resp = client.get("/api/v1/ping-db", params={"company": "ACME"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_ping_db_failure_returns_500(client, monkeypatch):
    def _boom(company):
        raise RuntimeError("no config")

    monkeypatch.setattr(health, "load_db_config", _boom)

    resp = client.get("/api/v1/ping-db", params={"company": "ACME"})
    assert resp.status_code == 500
