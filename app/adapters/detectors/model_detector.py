import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.adapters.detectors.rule_detector import DetectorThresholds
from app.domain.models import Decision, RiskAssessment, build_empty_text_assessment
from app.storage.s3 import download_directory_if_configured

logger = logging.getLogger(__name__)


@dataclass
class _ModelRuntime:
    tokenizer: Any
    model: Any
    torch: Any


class BertDetector:
    def __init__(
        self,
        thresholds: DetectorThresholds,
        model_path: str,
        model_name: str,
        model_s3_uri: str | None,
        model_device: int,
    ) -> None:
        self._thresholds = thresholds
        self._model_path = model_path
        self._model_name = model_name
        self._model_s3_uri = model_s3_uri
        self._model_device = model_device
        self._runtime: _ModelRuntime | None = None

    def warmup(self) -> None:
        self._ensure_runtime()

    def detect(self, text: str) -> RiskAssessment:
        normalized = text.strip()
        if not normalized:
            return build_empty_text_assessment("bert")

        runtime = self._ensure_runtime()

        encoded = runtime.tokenizer(
            normalized,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        )
        with runtime.torch.no_grad():
            output = runtime.model(**encoded)
            probability = runtime.torch.softmax(output.logits, dim=1)[0][1].item()

        if probability >= self._thresholds.block:
            return RiskAssessment(
                Decision.BLOCK,
                probability,
                "bert_risk_high",
                detector_used="bert",
                detector_details={"model_score": probability},
            )
        if probability >= self._thresholds.allow:
            return RiskAssessment(
                Decision.REVIEW,
                probability,
                "bert_risk_medium",
                detector_used="bert",
                detector_details={"model_score": probability},
            )
        return RiskAssessment(
            Decision.ALLOW,
            probability,
            "bert_risk_low",
            detector_used="bert",
            detector_details={"model_score": probability},
        )

    def _ensure_runtime(self) -> _ModelRuntime:
        if self._runtime is not None:
            return self._runtime

        load_path = self._resolve_model_path()
        if not self._has_required_artifacts(load_path):
            if self._model_s3_uri:
                logger.info(
                    "Model checkpoint is missing or incomplete at %s, downloading from S3: %s",
                    load_path,
                    self._model_s3_uri,
                )
                downloaded_any = download_directory_if_configured(load_path, self._model_s3_uri)
                if downloaded_any:
                    logger.info("Downloaded model artifacts from S3 into %s", load_path)
            if not self._has_required_artifacts(load_path):
                raise RuntimeError(
                    "Could not load classification model from MODEL_PATH. "
                    "Provide a valid fine-tuned checkpoint or configure MODEL_S3_URI."
                )

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ModuleNotFoundError as error:
            raise RuntimeError("BERT dependencies are not installed") from error

        try:
            tokenizer = AutoTokenizer.from_pretrained(str(load_path))
            model = AutoModelForSequenceClassification.from_pretrained(str(load_path))
        except Exception as error:
            raise RuntimeError(
                "Could not load classification model from MODEL_PATH. "
                "Provide a valid fine-tuned checkpoint or configure MODEL_S3_URI."
            ) from error

        if self._model_device >= 0 and torch.cuda.is_available():
            model.to(self._model_device)

        model.eval()
        self._runtime = _ModelRuntime(tokenizer=tokenizer, model=model, torch=torch)
        return self._runtime

    def _resolve_model_path(self) -> Path:
        model_dir = Path(self._model_path)
        if self._has_required_artifacts(model_dir):
            return model_dir

        cache_root = Path(os.environ.get("MODEL_CACHE_DIR", "/tmp/confidential-model-cache"))
        cache_dir = cache_root / model_dir.name
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @staticmethod
    def _has_required_artifacts(model_dir: Path) -> bool:
        if not model_dir.exists() or not model_dir.is_dir():
            return False

        required_files = {
            "config.json",
            "tokenizer_config.json",
        }
        if not required_files.issubset(
            {path.name for path in model_dir.iterdir() if path.is_file()}
        ):
            return False

        has_weights = any(
            (model_dir / filename).is_file()
            for filename in ("model.safetensors", "pytorch_model.bin")
        )
        has_tokenizer = any(
            (model_dir / filename).is_file()
            for filename in ("tokenizer.json", "vocab.txt", "sentencepiece.bpe.model")
        )
        return has_weights and has_tokenizer
