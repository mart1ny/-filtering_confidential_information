from app.infrastructure.monitoring.metrics import metrics_response


def test_metrics_response_returns_prometheus_media_type() -> None:
    response = metrics_response()

    assert response.status_code == 200
    assert "text/plain" in response.media_type
