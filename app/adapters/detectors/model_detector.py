from dataclasses import dataclass
from typing import Any

from app.adapters.detectors.rule_detector import DetectorThresholds
from app.domain.models import Decision, RiskAssessment, build_empty_text_assessment


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
        model_device: int,
    ) -> None:
        self._thresholds = thresholds
        self._model_path = model_path
        self._model_name = model_name
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

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ModuleNotFoundError as error:
            raise RuntimeError("BERT dependencies are not installed") from error

        try:
            tokenizer = AutoTokenizer.from_pretrained(self._model_path)
            model = AutoModelForSequenceClassification.from_pretrained(self._model_path)
        except Exception as error:
            raise RuntimeError(
                "Could not load classification model from MODEL_PATH. "
                "Provide a valid fine-tuned checkpoint."
            ) from error

        if self._model_device >= 0 and torch.cuda.is_available():
            model.to(self._model_device)

        model.eval()
        self._runtime = _ModelRuntime(tokenizer=tokenizer, model=model, torch=torch)
        return self._runtime
