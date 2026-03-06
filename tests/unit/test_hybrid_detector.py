from app.adapters.detectors.hybrid_detector import HybridDetector
from app.domain.models import Decision, RiskAssessment


class StubRules:
    def __init__(self, result: RiskAssessment) -> None:
        self._result = result

    def detect(self, text: str) -> RiskAssessment:
        return self._result


class StubModel:
    def __init__(self, result: RiskAssessment) -> None:
        self._result = result

    def detect(self, text: str) -> RiskAssessment:
        return self._result


def test_hybrid_returns_rules_block_immediately() -> None:
    detector = HybridDetector(
        rules_detector=StubRules(RiskAssessment(Decision.BLOCK, 0.95, "token_pattern")),
        model_detector=StubModel(RiskAssessment(Decision.ALLOW, 0.1, "bert_risk_low")),
    )
    result = detector.detect("secret")
    assert result.decision == Decision.BLOCK
    assert result.reason == "token_pattern"


def test_hybrid_returns_model_when_model_risk_is_higher() -> None:
    detector = HybridDetector(
        rules_detector=StubRules(RiskAssessment(Decision.REVIEW, 0.55, "email_pattern")),
        model_detector=StubModel(RiskAssessment(Decision.BLOCK, 0.81, "bert_risk_high")),
    )
    result = detector.detect("text")
    assert result.decision == Decision.BLOCK
    assert result.reason == "bert_risk_high"


def test_hybrid_keeps_rules_when_rules_risk_is_higher() -> None:
    detector = HybridDetector(
        rules_detector=StubRules(RiskAssessment(Decision.REVIEW, 0.6, "email_pattern")),
        model_detector=StubModel(RiskAssessment(Decision.ALLOW, 0.2, "bert_risk_low")),
    )
    result = detector.detect("text")
    assert result.decision == Decision.REVIEW
    assert result.reason == "rules_email_pattern"
