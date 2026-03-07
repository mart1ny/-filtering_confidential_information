from __future__ import annotations

import builtins
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from app.adapters.detectors.model_detector import BertDetector, _ModelRuntime
from app.adapters.detectors.rule_detector import DetectorThresholds
from app.domain.models import Decision


class _NoGrad:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: object) -> None:
        return None


class _ItemValue:
    def __init__(self, value: float) -> None:
        self._value = value

    def item(self) -> float:
        return self._value


@dataclass
class _FakeSoftmaxResult:
    positive_probability: float

    def __getitem__(self, index: int) -> Any:
        if index == 0:
            return [None, _ItemValue(self.positive_probability)]
        raise IndexError(index)


class _FakeTorch:
    def __init__(self, positive_probability: float, cuda_available: bool = False) -> None:
        self._positive_probability = positive_probability
        self.cuda = SimpleNamespace(is_available=lambda: cuda_available)

    def no_grad(self) -> _NoGrad:
        return _NoGrad()

    def softmax(self, _: object, dim: int) -> _FakeSoftmaxResult:
        assert dim == 1
        return _FakeSoftmaxResult(self._positive_probability)


class _FakeModel:
    def __init__(self) -> None:
        self.sent_to_device: int | None = None
        self.eval_called = False

    def __call__(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(logits=[[0.0, 1.0]])

    def to(self, device: int) -> None:
        self.sent_to_device = device

    def eval(self) -> None:
        self.eval_called = True


class _FakeTokenizer:
    def __init__(self) -> None:
        self.last_text: str | None = None

    def __call__(self, text: str, **_: object) -> dict[str, list[int]]:
        self.last_text = text
        return {"input_ids": [1, 2]}


def _build_detector() -> BertDetector:
    return BertDetector(
        thresholds=DetectorThresholds(allow=0.3, block=0.7),
        model_path="local-model",
        model_name="remote-model",
        model_device=-1,
    )


def test_detect_returns_allow_for_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    detector = _build_detector()
    monkeypatch.setattr(
        detector, "_ensure_runtime", lambda: (_ for _ in ()).throw(RuntimeError("no runtime"))
    )

    result = detector.detect("   ")

    assert result.decision == Decision.ALLOW
    assert result.reason == "empty_text"
    assert result.risk_score == 0.0


@pytest.mark.parametrize(
    ("probability", "expected_decision", "expected_reason"),
    [
        (0.91, Decision.BLOCK, "bert_risk_high"),
        (0.55, Decision.REVIEW, "bert_risk_medium"),
        (0.10, Decision.ALLOW, "bert_risk_low"),
    ],
)
def test_detect_maps_probability_to_decision(
    probability: float,
    expected_decision: Decision,
    expected_reason: str,
) -> None:
    detector = _build_detector()
    runtime = _ModelRuntime(
        tokenizer=_FakeTokenizer(),
        model=_FakeModel(),
        torch=_FakeTorch(positive_probability=probability),
    )
    detector._runtime = runtime

    result = detector.detect(" message ")

    assert result.decision == expected_decision
    assert result.reason == expected_reason
    assert result.risk_score == probability


def test_ensure_runtime_raises_when_dependencies_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = _build_detector()
    original_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in {"torch", "transformers"}:
            raise ModuleNotFoundError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="BERT dependencies are not installed"):
        detector._ensure_runtime()


def test_ensure_runtime_falls_back_to_model_name_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = BertDetector(
        thresholds=DetectorThresholds(allow=0.3, block=0.7),
        model_path="missing-local",
        model_name="remote-model",
        model_device=0,
    )
    fake_model = _FakeModel()
    calls: list[tuple[str, str, dict[str, object]]] = []

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(name: str) -> _FakeTokenizer:
            calls.append(("tokenizer", name, {}))
            if name == "missing-local":
                raise OSError("not found")
            return _FakeTokenizer()

    class AutoModelForSequenceClassification:
        @staticmethod
        def from_pretrained(name: str, **kwargs: object) -> _FakeModel:
            calls.append(("model", name, kwargs))
            if name == "missing-local":
                raise OSError("not found")
            return fake_model

    transformers_module = ModuleType("transformers")
    transformers_module.AutoTokenizer = AutoTokenizer
    transformers_module.AutoModelForSequenceClassification = AutoModelForSequenceClassification
    torch_module = _FakeTorch(positive_probability=0.2, cuda_available=True)

    monkeypatch.setitem(__import__("sys").modules, "transformers", transformers_module)
    monkeypatch.setitem(__import__("sys").modules, "torch", torch_module)

    runtime_first = detector._ensure_runtime()
    runtime_second = detector._ensure_runtime()

    assert runtime_first is runtime_second
    assert fake_model.sent_to_device == 0
    assert fake_model.eval_called is True
    assert calls == [
        ("tokenizer", "missing-local", {}),
        ("tokenizer", "remote-model", {}),
        ("model", "remote-model", {"num_labels": 2}),
    ]
