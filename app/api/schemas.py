from pydantic import BaseModel, Field

from app.domain.models import Decision, ReviewStatus


class AssessRequest(BaseModel):
    text: str = Field(min_length=1)


class AssessResponse(BaseModel):
    decision: Decision
    risk_score: float
    reason: str
    review_case_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str


class DriftMetricRequest(BaseModel):
    psi: float = Field(ge=0)
    csi: float = Field(ge=0)


class ReviewCaseResponse(BaseModel):
    case_id: str
    text: str
    risk_score: float
    detector_decision: Decision
    reason: str
    status: ReviewStatus
    is_contains_confidential: int | None
    reviewer: str | None
    note: str | None
    created_at: str
    reviewed_at: str | None


class ReviewLabelRequest(BaseModel):
    is_contains_confidential: int = Field(ge=0, le=1)
    reviewer: str | None = None
    note: str | None = None
