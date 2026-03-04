from pydantic import BaseModel, Field

from app.domain.models import Decision


class AssessRequest(BaseModel):
    text: str = Field(min_length=1)


class AssessResponse(BaseModel):
    decision: Decision
    risk_score: float
    reason: str


class HealthResponse(BaseModel):
    status: str
    service: str


class DriftMetricRequest(BaseModel):
    psi: float = Field(ge=0)
    csi: float = Field(ge=0)
