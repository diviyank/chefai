from fastapi.testclient import TestClient


def test_startup_marks_stale_running(monkeypatch):
    called = {}
    from app import jobs
    monkeypatch.setattr(jobs, "mark_stale_running", lambda: called.setdefault("ok", True))
    from app.main import app
    with TestClient(app):  # triggers startup
        pass
    assert called.get("ok") is True
