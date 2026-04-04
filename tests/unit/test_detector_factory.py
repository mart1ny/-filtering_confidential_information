from app.adapters.detectors.factory import build_text_detector
from app.adapters.detectors.hybrid_detector import HybridDetector
from app.adapters.detectors.model_detector import BertDetector
from app.adapters.detectors.rule_detector import RuleBasedDetector
from app.infrastructure.config.settings import Settings


def build_settings(backend: str) -> Settings:
    return Settings(
        APP_NAME="svc",
        APP_ENV="test",
        APP_HOST="0.0.0.0",
        APP_PORT=8000,
        RISK_ALLOW_THRESHOLD=0.3,
        RISK_BLOCK_THRESHOLD=0.7,
        DETECTOR_BACKEND=backend,
        MODEL_PATH="bert_classifier/model",
        MODEL_NAME="distilbert-base-uncased",
        MODEL_S3_URI=None,
        MODEL_DEVICE=-1,
    )


def test_factory_builds_rules_backend() -> None:
    detector = build_text_detector(build_settings("rules"))
    assert isinstance(detector, RuleBasedDetector)


def test_factory_builds_bert_backend(monkeypatch) -> None:
    monkeypatch.setattr(BertDetector, "warmup", lambda self: None)
    detector = build_text_detector(build_settings("bert"))
    assert isinstance(detector, BertDetector)


def test_factory_builds_hybrid_backend(monkeypatch) -> None:
    monkeypatch.setattr(BertDetector, "warmup", lambda self: None)
    detector = build_text_detector(build_settings("hybrid"))
    assert isinstance(detector, HybridDetector)


def test_factory_falls_back_to_hybrid_on_unknown_backend(monkeypatch) -> None:
    monkeypatch.setattr(BertDetector, "warmup", lambda self: None)
    detector = build_text_detector(build_settings("unknown"))
    assert isinstance(detector, HybridDetector)


def test_factory_falls_back_to_rules_when_model_init_fails(monkeypatch) -> None:
    def broken_init(
        self: object,
        thresholds: tuple[float, float],
        model_path: str,
        model_name: str,
        model_s3_uri: str | None,
        model_device: int,
    ) -> None:
        _ = (self, thresholds, model_path, model_name, model_s3_uri, model_device)
        raise RuntimeError("broken")

    monkeypatch.setattr(BertDetector, "__init__", broken_init)
    detector = build_text_detector(build_settings("bert"))
    assert isinstance(detector, RuleBasedDetector)


def test_factory_uses_hybrid_when_backend_is_blank(monkeypatch) -> None:
    monkeypatch.setattr(BertDetector, "warmup", lambda self: None)
    detector = build_text_detector(build_settings(""))
    assert isinstance(detector, HybridDetector)
