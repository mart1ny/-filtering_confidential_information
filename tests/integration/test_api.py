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
    assert payload["detector_used"] in {"rules", "bert", "hybrid"}
    assert isinstance(payload["detector_details"], dict)
