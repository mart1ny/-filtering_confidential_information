from typing import Protocol

from app.domain.models import RiskAssessment


class TextDetector(Protocol):
    def detect(self, text: str) -> RiskAssessment:
        """Return risk assessment for a text payload."""
