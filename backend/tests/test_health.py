"""Smoke test: the app boots and /health responds.

First test in the repo — proves the skeleton wiring (config → app → endpoint)
works end to end before we build features on top of it.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "environment" in body
