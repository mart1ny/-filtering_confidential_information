from time import perf_counter

from fastapi import APIRouter, Depends, FastAPI

from app.adapters.detectors.factory import build_text_detector
from app.api.schemas import AssessRequest, AssessResponse, DriftMetricRequest, HealthResponse
from app.application.use_cases.assess_text import AssessTextUseCase
from app.infrastructure.config.settings import settings
from app.infrastructure.monitoring.metrics import (
    ML_QUALITY_SCORE,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    metrics_response,
)


def get_use_case() -> AssessTextUseCase:
    detector = build_text_detector(settings)
    return AssessTextUseCase(detector=detector)


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name)


@router.post("/v1/assess", response_model=AssessResponse)
def assess(
    request: AssessRequest, use_case: AssessTextUseCase = Depends(get_use_case)
) -> AssessResponse:
    started = perf_counter()
    assessment = use_case.execute(request.text)
    REQUEST_COUNT.labels(endpoint="assess", decision=assessment.decision.value).inc()
    REQUEST_LATENCY.labels(endpoint="assess").observe(perf_counter() - started)
    return AssessResponse(
        decision=assessment.decision,
        risk_score=assessment.risk_score,
        reason=assessment.reason,
    )


@router.post("/v1/metrics/drift")
def ingest_drift(payload: DriftMetricRequest) -> dict[str, str]:
    psi_bucket = "high" if payload.psi >= 0.2 else "low"
    csi_bucket = "high" if payload.csi >= 0.2 else "low"
    ML_QUALITY_SCORE.labels(metric_name="psi", bucket=psi_bucket).inc()
    ML_QUALITY_SCORE.labels(metric_name="csi", bucket=csi_bucket).inc()
    REQUEST_COUNT.labels(endpoint="drift", decision="n/a").inc()
    return {"status": "accepted"}


@router.get("/metrics")
def metrics() -> object:
    return metrics_response()


def build_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.include_router(router)
    return app
