from app.domain.models import Decision, RiskAssessment


class HybridDetector:
    def __init__(self, rules_detector, model_detector) -> None:
        self._rules_detector = rules_detector
        self._model_detector = model_detector

    def detect(self, text: str) -> RiskAssessment:
        rules_result = self._rules_detector.detect(text)
        if rules_result.decision == Decision.BLOCK:
            return rules_result

        model_result = self._model_detector.detect(text)
        if model_result.risk_score >= rules_result.risk_score:
            return model_result
        return RiskAssessment(
            rules_result.decision, rules_result.risk_score, f"rules_{rules_result.reason}"
        )
