from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "conf_filter_requests_total",
    "Total number of requests processed",
    ["endpoint", "decision"],
)

REQUEST_LATENCY = Histogram(
    "conf_filter_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint"],
)

ML_QUALITY_SCORE = Counter(
    "conf_filter_ml_metric_events_total",
    "ML metric events",
    ["metric_name", "bucket"],
)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
