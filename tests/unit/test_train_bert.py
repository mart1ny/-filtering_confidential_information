from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest


def _import_train_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    if "app.training.train_bert" in sys.modules:
        del sys.modules["app.training.train_bert"]

    class DummyDataset:
        def __init__(self, frame: pd.DataFrame) -> None:
            self.frame = frame
            self.map_calls: list[dict[str, object]] = []

        @classmethod
        def from_pandas(cls, frame: pd.DataFrame, preserve_index: bool = False) -> "DummyDataset":
            assert preserve_index is False
            return cls(frame.copy())

        def map(self, func: object, batched: bool = False) -> "DummyDataset":
            assert batched is True
            mapper = func
            assert callable(mapper)
            batch = {"text": self.frame["text"].tolist()}
            mapped = mapper(batch)
            self.map_calls.append({"batched": batched, "mapped": mapped})
            return self

    datasets_module = ModuleType("datasets")
    datasets_module.Dataset = DummyDataset

    class _AutoTokenizer:
        @staticmethod
        def from_pretrained(_: str) -> object:
            return object()

    class _AutoModel:
        @staticmethod
        def from_pretrained(_: str, **__: object) -> object:
            return object()

    class _DataCollatorWithPadding:
        def __init__(self, tokenizer: object) -> None:
            self.tokenizer = tokenizer

    class _TrainingArguments:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class _Trainer:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    transformers_module = ModuleType("transformers")
    transformers_module.AutoModelForSequenceClassification = _AutoModel
    transformers_module.AutoTokenizer = _AutoTokenizer
    transformers_module.DataCollatorWithPadding = _DataCollatorWithPadding
    transformers_module.EvalPrediction = object
    transformers_module.Trainer = _Trainer
    transformers_module.TrainingArguments = _TrainingArguments
    transformers_module.set_seed = lambda _: None

    monkeypatch.setitem(sys.modules, "datasets", datasets_module)
    monkeypatch.setitem(sys.modules, "transformers", transformers_module)

    return importlib.import_module("app.training.train_bert")


def test_build_config_overrides_runtime_args(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _import_train_module(monkeypatch)
    args = SimpleNamespace(
        data_path="dataset/custom.parquet",
        output_dir="artifacts/custom",
        model_name="distilbert-base-uncased",
        max_length=128,
        train_batch_size=8,
        eval_batch_size=16,
        epochs=4,
        learning_rate=1e-4,
        seed=7,
    )

    config = module.build_config(args)

    assert str(config.data_path) == "dataset/custom.parquet"
    assert str(config.output_dir) == "artifacts/custom"
    assert config.model_name == "distilbert-base-uncased"
    assert config.max_length == 128
    assert config.train_batch_size == 8
    assert config.eval_batch_size == 16
    assert config.epochs == 4
    assert config.learning_rate == 1e-4
    assert config.seed == 7


def test_pandas_to_hf_renames_label_column(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _import_train_module(monkeypatch)
    frame = pd.DataFrame({"text": ["a"], "is_contains_confidential": [1], "id": [10]})

    dataset = module.pandas_to_hf(
        frame, text_column="text", label_column="is_contains_confidential"
    )

    assert dataset.frame.columns.tolist() == ["text", "labels"]
    assert dataset.frame["labels"].tolist() == [1]


def test_tokenize_dataset_uses_batched_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _import_train_module(monkeypatch)
    dataset = module.Dataset.from_pandas(
        pd.DataFrame({"text": ["hello"], "labels": [0]}),
        preserve_index=False,
    )

    class Tokenizer:
        def __call__(self, texts: list[str], **kwargs: object) -> dict[str, list[int]]:
            assert texts == ["hello"]
            assert kwargs["truncation"] is True
            assert kwargs["max_length"] == 256
            return {"input_ids": [1]}

    tokenized = module.tokenize_dataset(
        dataset=dataset,
        tokenizer=Tokenizer(),
        text_column="text",
        max_length=256,
    )

    assert tokenized.map_calls[0]["batched"] is True
    assert tokenized.map_calls[0]["mapped"] == {"input_ids": [1]}


def test_save_metrics_persists_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _import_train_module(monkeypatch)
    target = tmp_path / "metrics"

    module.save_metrics({"f1": 0.8}, target, "val_metrics.json")

    payload = json.loads((target / "val_metrics.json").read_text(encoding="utf-8"))
    assert payload == {"f1": 0.8}


def test_softmax_logits_rows_sum_to_one(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _import_train_module(monkeypatch)
    logits = np.array([[1.0, 2.0], [5.0, 1.0]])

    probs = module.softmax_logits(logits)

    np.testing.assert_allclose(np.sum(probs, axis=1), np.array([1.0, 1.0]))


def test_main_runs_training_orchestration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _import_train_module(monkeypatch)
    output_dir = tmp_path / "artifacts"
    fake_config = SimpleNamespace(
        data_path=Path("dataset/ds.parquet"),
        output_dir=output_dir,
        model_name="distilbert-base-uncased",
        text_column="text",
        label_column="is_contains_confidential",
        group_column="id",
        max_length=128,
        train_batch_size=8,
        eval_batch_size=8,
        epochs=1,
        learning_rate=2e-5,
        weight_decay=0.01,
        warmup_ratio=0.1,
        logging_steps=1,
        eval_steps=2,
        save_steps=2,
        seed=11,
        test_size=0.2,
        val_size=0.2,
    )
    train_frame = pd.DataFrame({"text": ["a"], "is_contains_confidential": [1], "id": [1]})
    val_frame = pd.DataFrame({"text": ["b"], "is_contains_confidential": [0], "id": [2]})
    test_frame = pd.DataFrame({"text": ["c"], "is_contains_confidential": [1], "id": [3]})
    calls: dict[str, Any] = {"save_metrics": []}

    class FakeTokenizer:
        @staticmethod
        def from_pretrained(name: str) -> "FakeTokenizer":
            calls["tokenizer_name"] = name
            return FakeTokenizer()

        def save_pretrained(self, path: str) -> None:
            calls["tokenizer_saved"] = path

    class FakeModel:
        @staticmethod
        def from_pretrained(name: str, **kwargs: object) -> str:
            calls["model_name"] = name
            calls["model_kwargs"] = kwargs
            return "model-object"

    class FakeTrainingArguments:
        def __init__(self, **kwargs: object) -> None:
            calls["training_arguments"] = kwargs

    class FakeTrainer:
        def __init__(self, **kwargs: object) -> None:
            calls["trainer_kwargs"] = kwargs

        def train(self) -> None:
            calls["train_called"] = True

        def evaluate(self, eval_dataset: object) -> dict[str, object]:
            calls["evaluate_dataset"] = eval_dataset
            return {"eval_loss": 0.2, "eval_f1": 0.9, "epoch": 1, "ignored": "text"}

        def predict(self, _: object) -> SimpleNamespace:
            return SimpleNamespace(
                predictions=np.array([[0.1, 0.9], [0.9, 0.1]]),
                label_ids=np.array([1, 0]),
            )

        def save_model(self, path: str) -> None:
            calls["model_saved"] = path

    monkeypatch.setattr(module, "parse_args", lambda: SimpleNamespace())
    monkeypatch.setattr(module, "build_config", lambda _args: fake_config)
    monkeypatch.setattr(module, "set_seed", lambda seed: calls.setdefault("seed", seed))
    monkeypatch.setattr(module, "load_dataset", lambda _: pd.DataFrame({"id": [1]}))
    monkeypatch.setattr(
        module,
        "split_by_group",
        lambda **_: SimpleNamespace(train=train_frame, val=val_frame, test=test_frame),
    )
    monkeypatch.setattr(module, "AutoTokenizer", FakeTokenizer)
    monkeypatch.setattr(module, "AutoModelForSequenceClassification", FakeModel)
    monkeypatch.setattr(module, "TrainingArguments", FakeTrainingArguments)
    monkeypatch.setattr(module, "Trainer", FakeTrainer)
    monkeypatch.setattr(
        module, "DataCollatorWithPadding", lambda tokenizer: {"tokenizer": tokenizer}
    )
    monkeypatch.setattr(module, "tokenize_dataset", lambda dataset, *_: dataset)
    monkeypatch.setattr(module, "evaluate_classification", lambda *_args, **_kwargs: {"f1": 0.8})
    monkeypatch.setattr(
        module,
        "save_metrics",
        lambda metrics, out_dir, name: calls["save_metrics"].append((metrics, out_dir, name)),
    )

    module.main()

    assert calls["seed"] == 11
    assert calls["tokenizer_name"] == "distilbert-base-uncased"
    assert calls["model_kwargs"] == {"num_labels": 2}
    assert calls["train_called"] is True
    assert calls["model_saved"] == str(output_dir / "model")
    assert calls["tokenizer_saved"] == str(output_dir / "model")
    assert calls["training_arguments"]["output_dir"] == str(output_dir / "checkpoints")
    assert calls["save_metrics"][0][2] == "val_metrics.json"
    assert calls["save_metrics"][0][0] == {"eval_loss": 0.2, "eval_f1": 0.9, "epoch": 1.0}
    assert calls["save_metrics"][1] == ({"f1": 0.8}, output_dir, "test_metrics.json")
