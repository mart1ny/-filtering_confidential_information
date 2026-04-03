from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


def test_review_queue_flow(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(routes.settings, "review_storage_dir", str(tmp_path))
    monkeypatch.setattr(routes.settings, "review_database_url", None)
    monkeypatch.setattr(routes.settings, "review_db_host", None)
    monkeypatch.setattr(routes.settings, "review_db_name", None)
    monkeypatch.setattr(routes.settings, "review_db_user", None)
    monkeypatch.setattr(routes.settings, "review_db_password", None)
    routes.get_review_store.cache_clear()
    client = TestClient(app)

    assess_response = client.post("/v1/assess", json={"text": "user@example.com"})

    assert assess_response.status_code == 200
    assess_payload = assess_response.json()
    assert assess_payload["decision"] == "review"
    assert assess_payload["review_case_id"] is not None

    queue_response = client.get("/v1/review-queue")
    assert queue_response.status_code == 200
    queue_payload = queue_response.json()
    assert len(queue_payload) == 1
    case_id = queue_payload[0]["case_id"]

    label_response = client.post(
        f"/v1/review-queue/{case_id}/label",
        json={"is_contains_confidential": 1, "reviewer": "admin", "note": "contains pii"},
    )
    assert label_response.status_code == 200
    assert label_response.json()["status"] == "labeled"

    export_response = client.post("/v1/review-dataset/export")
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "exported"

    routes.get_review_store.cache_clear()
