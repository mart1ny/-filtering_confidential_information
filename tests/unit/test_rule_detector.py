from app.adapters.detectors.rule_detector import DetectorThresholds, RuleBasedDetector
from app.domain.models import Decision


def build_detector() -> RuleBasedDetector:
    return RuleBasedDetector(DetectorThresholds(allow=0.3, block=0.7))


def test_blocks_token() -> None:
    detector = build_detector()
    result = detector.detect("my token is sk_ABC1234567890")
    assert result.decision == Decision.BLOCK
    assert result.reason == "token_pattern"


def test_blocks_luhn_valid_card() -> None:
    detector = build_detector()
    result = detector.detect("pay with 4111 1111 1111 1111 now")
    assert result.decision == Decision.BLOCK
    assert result.reason == "bank_card_pattern"


def test_reviews_email() -> None:
    detector = build_detector()
    result = detector.detect("contact me: user@example.com")
    assert result.decision == Decision.REVIEW


def test_allows_clean_text() -> None:
    detector = build_detector()
    result = detector.detect("hello world")
    assert result.decision == Decision.ALLOW
