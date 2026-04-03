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


def test_drift_endpoint() -> None:
    client = TestClient(app)
    response = client.post("/v1/metrics/drift", json={"psi": 0.1, "csi": 0.3})
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_metrics_endpoint_returns_prometheus_payload() -> None:
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "conf_filter_requests_total" in response.text
