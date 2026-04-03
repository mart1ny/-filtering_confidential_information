from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    LABELED = "labeled"


@dataclass(frozen=True)
class RiskAssessment:
    decision: Decision
    risk_score: float
    reason: str


@dataclass(frozen=True)
class ReviewCase:
    case_id: str
    text: str
    risk_score: float
    detector_decision: Decision
    reason: str
    status: ReviewStatus
    is_contains_confidential: int | None
    reviewer: str | None
    note: str | None
    created_at: datetime
    reviewed_at: datetime | None
