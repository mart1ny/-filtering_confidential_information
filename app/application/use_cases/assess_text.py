from dataclasses import dataclass

from app.domain.interfaces import TextDetector
from app.domain.models import RiskAssessment


@dataclass(frozen=True)
class AssessTextUseCase:
    detector: TextDetector

    def execute(self, text: str) -> RiskAssessment:
        return self.detector.detect(text)
