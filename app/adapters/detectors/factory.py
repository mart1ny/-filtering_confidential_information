import logging

from app.adapters.detectors.hybrid_detector import HybridDetector
from app.adapters.detectors.model_detector import BertDetector
from app.adapters.detectors.rule_detector import DetectorThresholds, RuleBasedDetector
from app.domain.interfaces import TextDetector
from app.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)


def build_text_detector(app_settings: Settings) -> TextDetector:
    thresholds = DetectorThresholds(
        allow=app_settings.risk_allow_threshold,
        block=app_settings.risk_block_threshold,
    )
    rules_detector = RuleBasedDetector(thresholds=thresholds)
    backend = (app_settings.detector_backend or "hybrid").strip().lower() or "hybrid"

    if backend == "rules":
        logger.info("Detector backend configured as rules-only")
        return rules_detector

    try:
        model_detector = BertDetector(
            thresholds=thresholds,
            model_path=app_settings.model_path,
            model_name=app_settings.model_name,
            model_s3_uri=app_settings.model_s3_uri,
            model_device=app_settings.model_device,
        )
        # Validate model runtime at startup to avoid per-request failures.
        model_detector.warmup()
    except RuntimeError as error:
        logger.warning("Falling back to rules detector because BERT warmup failed: %s", error)
        return rules_detector

    if backend == "bert":
        logger.info("Detector backend configured as bert-only")
        return model_detector
    if backend == "hybrid":
        logger.info("Detector backend configured as hybrid with model priority")
        return HybridDetector(rules_detector=rules_detector, model_detector=model_detector)

    logger.info("Unknown detector backend '%s', using hybrid with model priority", backend)
    return HybridDetector(rules_detector=rules_detector, model_detector=model_detector)
