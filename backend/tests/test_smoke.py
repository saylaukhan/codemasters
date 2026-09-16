"""Smoke test: the application starts and answers ``GET /api/health``."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app import __version__
from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    reported_at = datetime.fromisoformat(body["time"])
    assert reported_at.tzinfo is not None
    assert reported_at.utcoffset() == UTC.utcoffset(None)
