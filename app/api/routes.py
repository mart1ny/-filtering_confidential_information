from functools import lru_cache
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, Depends, FastAPI, HTTPException

from app.adapters.detectors.factory import build_text_detector
from app.api.schemas import (
    AssessRequest,
    AssessResponse,
    DriftMetricRequest,
    HealthResponse,
    ReviewCaseResponse,
    ReviewLabelRequest,
)
from app.application.use_cases.assess_text import AssessTextUseCase
from app.domain.models import Decision, ReviewCase, ReviewStatus
from app.infrastructure.config.settings import settings
from app.infrastructure.monitoring.metrics import (
    ML_QUALITY_SCORE,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    metrics_response,
)
from app.review.store import ReviewQueueStore


@lru_cache(maxsize=1)
def get_use_case() -> AssessTextUseCase:
    detector = build_text_detector(settings)
    return AssessTextUseCase(detector=detector)


@lru_cache(maxsize=1)
def get_review_store() -> ReviewQueueStore:
    return ReviewQueueStore(
        storage_dir=settings.review_storage_dir,
        database_url=settings.resolved_review_database_url,
    )


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name)


@router.post("/v1/assess", response_model=AssessResponse)
def assess(
    request: AssessRequest,
    use_case: AssessTextUseCase = Depends(get_use_case),
    review_store: ReviewQueueStore = Depends(get_review_store),
) -> AssessResponse:
    started = perf_counter()
    assessment = use_case.execute(request.text)
    REQUEST_COUNT.labels(endpoint="assess", decision=assessment.decision.value).inc()
    REQUEST_LATENCY.labels(endpoint="assess").observe(perf_counter() - started)
    review_case_id: str | None = None
    if assessment.decision == Decision.REVIEW:
        review_case = review_store.create_case(
            text=request.text,
            risk_score=assessment.risk_score,
            detector_decision=assessment.decision,
            reason=assessment.reason,
        )
        review_case_id = review_case.case_id
    return AssessResponse(
        decision=assessment.decision,
        risk_score=assessment.risk_score,
        reason=assessment.reason,
        review_case_id=review_case_id,
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


@router.get("/v1/review-queue", response_model=list[ReviewCaseResponse])
def list_review_queue(
    status: ReviewStatus | None = None,
    review_store: ReviewQueueStore = Depends(get_review_store),
) -> list[ReviewCaseResponse]:
    return [_to_review_case_response(case) for case in review_store.list_cases(status=status)]


@router.post("/v1/review-queue/{case_id}/label", response_model=ReviewCaseResponse)
def label_review_case(
    case_id: str,
    payload: ReviewLabelRequest,
    review_store: ReviewQueueStore = Depends(get_review_store),
) -> ReviewCaseResponse:
    try:
        case = review_store.label_case(
            case_id=case_id,
            is_contains_confidential=payload.is_contains_confidential,
            reviewer=payload.reviewer,
            note=payload.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_review_case_response(case)


@router.post("/v1/review-dataset/export")
def export_review_dataset(
    review_store: ReviewQueueStore = Depends(get_review_store),
) -> dict[str, str]:
    output_path = Path(settings.review_storage_dir) / "training_dataset.parquet"
    try:
        artifact = review_store.export_labeled_dataset(str(output_path))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "exported", "path": str(artifact)}


def build_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.include_router(router)
    return app


def _to_review_case_response(case: ReviewCase) -> ReviewCaseResponse:
    return ReviewCaseResponse(
        case_id=case.case_id,
        text=case.text,
        risk_score=case.risk_score,
        detector_decision=case.detector_decision,
        reason=case.reason,
        status=case.status,
        is_contains_confidential=case.is_contains_confidential,
        reviewer=case.reviewer,
        note=case.note,
        created_at=case.created_at.isoformat(),
        reviewed_at=case.reviewed_at.isoformat() if case.reviewed_at else None,
    )
