from app.adapters.detectors.hybrid_detector import HybridDetector
from app.adapters.detectors.model_detector import BertDetector
from app.adapters.detectors.rule_detector import DetectorThresholds, RuleBasedDetector
from app.infrastructure.config.settings import Settings


def build_text_detector(app_settings: Settings):
    thresholds = DetectorThresholds(
        allow=app_settings.risk_allow_threshold,
        block=app_settings.risk_block_threshold,
    )
    rules_detector = RuleBasedDetector(thresholds=thresholds)
    backend = app_settings.detector_backend.lower()

    if backend == "rules":
        return rules_detector

    try:
        model_detector = BertDetector(
            thresholds=thresholds,
            model_path=app_settings.model_path,
            model_name=app_settings.model_name,
            model_device=app_settings.model_device,
        )
    except Exception:
        return rules_detector

    if backend == "bert":
        return model_detector
    if backend == "hybrid":
        return HybridDetector(rules_detector=rules_detector, model_detector=model_detector)

    return rules_detector
