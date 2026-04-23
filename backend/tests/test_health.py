"""Health endpoint smoke tests."""

from fastapi.testclient import TestClient

from app.main import app


def test_live_probe() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_probe() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ready"
    assert body["cache_mode"] in {"memory", "redis"}
