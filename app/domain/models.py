from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


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
    detector_used: str = "unknown"
    detector_details: dict[str, Any] | None = None


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


def build_empty_text_assessment(detector_used: str) -> RiskAssessment:
    return RiskAssessment(
        Decision.ALLOW,
        0.0,
        "empty_text",
        detector_used=detector_used,
        detector_details={"empty_text": True},
    )
