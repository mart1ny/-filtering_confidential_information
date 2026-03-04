import re
from dataclasses import dataclass

from app.domain.models import Decision, RiskAssessment


@dataclass(frozen=True)
class DetectorThresholds:
    allow: float
    block: float


class RuleBasedDetector:
    def __init__(self, thresholds: DetectorThresholds) -> None:
        self._thresholds = thresholds
        self._card = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
        self._email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        self._passport = re.compile(r"\b\d{2}\s?\d{2}\s?\d{6}\b")
        self._token = re.compile(r"\b(?:sk|api|token)[-_]?[A-Za-z0-9]{10,}\b", re.IGNORECASE)

    def detect(self, text: str) -> RiskAssessment:
        normalized = text.strip()
        if not normalized:
            return RiskAssessment(Decision.ALLOW, 0.0, "empty_text")

        if self._token.search(normalized):
            return RiskAssessment(Decision.BLOCK, 0.95, "token_pattern")
        if self._passport.search(normalized):
            return RiskAssessment(Decision.BLOCK, 0.92, "passport_pattern")
        if self._has_valid_card(normalized):
            return RiskAssessment(Decision.BLOCK, 0.99, "bank_card_pattern")
        if self._email.search(normalized):
            return self._decision_from_score(0.55, "email_pattern")

        return self._decision_from_score(0.1, "no_sensitive_pattern")

    def _decision_from_score(self, score: float, reason: str) -> RiskAssessment:
        if score >= self._thresholds.block:
            return RiskAssessment(Decision.BLOCK, score, reason)
        if score >= self._thresholds.allow:
            return RiskAssessment(Decision.REVIEW, score, reason)
        return RiskAssessment(Decision.ALLOW, score, reason)

    def _has_valid_card(self, text: str) -> bool:
        for candidate in self._card.findall(text):
            digits = re.sub(r"\D", "", candidate)
            if 13 <= len(digits) <= 19 and self._luhn_is_valid(digits):
                return True
        return False

    def _luhn_is_valid(self, number: str) -> bool:
        total = 0
        parity = len(number) % 2
        for index, char in enumerate(number):
            digit = int(char)
            if index % 2 == parity:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        return total % 10 == 0
