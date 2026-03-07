from app.adapters.detectors.rule_detector import DetectorThresholds, RuleBasedDetector
from app.application.use_cases.assess_text import AssessTextUseCase
from app.domain.models import Decision


def test_use_case_returns_domain_object() -> None:
    use_case = AssessTextUseCase(
        detector=RuleBasedDetector(DetectorThresholds(allow=0.3, block=0.7))
    )
    result = use_case.execute("passport 1234 567890")
    assert result.decision == Decision.BLOCK
