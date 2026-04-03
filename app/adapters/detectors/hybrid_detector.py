from app.domain.interfaces import TextDetector
from app.domain.models import Decision, RiskAssessment


class HybridDetector:
    def __init__(self, rules_detector: TextDetector, model_detector: TextDetector) -> None:
        self._rules_detector = rules_detector
        self._model_detector = model_detector

    def detect(self, text: str) -> RiskAssessment:
        model_result = self._model_detector.detect(text)
        rules_result = self._rules_detector.detect(text)
        if model_result.decision != Decision.ALLOW:
            return RiskAssessment(
                model_result.decision,
                model_result.risk_score,
                model_result.reason,
                detector_used="bert",
                detector_details={
                    "strategy": "model_priority",
                    "model_score": model_result.risk_score,
                    "rules_score": rules_result.risk_score,
                    "rules_reason": rules_result.reason,
                    "rules_decision": rules_result.decision.value,
                },
            )

        if rules_result.decision == Decision.BLOCK:
            return RiskAssessment(
                Decision.REVIEW,
                max(model_result.risk_score, rules_result.risk_score),
                f"rules_flag_{rules_result.reason}",
                detector_used="hybrid",
                detector_details={
                    "strategy": "model_priority_with_rule_escalation",
                    "model_score": model_result.risk_score,
                    "rules_score": rules_result.risk_score,
                    "rules_reason": rules_result.reason,
                    "rules_decision": rules_result.decision.value,
                },
            )

        if model_result.risk_score >= rules_result.risk_score:
            return model_result
        return RiskAssessment(
            rules_result.decision,
            rules_result.risk_score,
            f"rules_{rules_result.reason}",
            detector_used="hybrid",
            detector_details={
                "strategy": "rules_support_signal",
                "model_score": model_result.risk_score,
                "rules_score": rules_result.risk_score,
                "rules_reason": rules_result.reason,
                "rules_decision": rules_result.decision.value,
            },
        )
