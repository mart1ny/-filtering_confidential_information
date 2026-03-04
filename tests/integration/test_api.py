from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_assess_endpoint() -> None:
    client = TestClient(app)
    response = client.post("/v1/assess", json={"text": "sk_secret0987654321"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "block"


def test_drift_endpoint() -> None:
    client = TestClient(app)
    response = client.post("/v1/metrics/drift", json={"psi": 0.1, "csi": 0.3})
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
