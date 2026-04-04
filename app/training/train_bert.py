from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from datasets import Dataset
from numpy.typing import NDArray
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EvalPrediction,
    Trainer,
    TrainingArguments,
    set_seed,
)

from app.storage.s3 import upload_directory_if_configured
from app.training.config import TrainingConfig
from app.training.data import load_dataset, split_by_group
from app.training.metrics import evaluate_classification, trainer_compute_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train BERT-style classifier for confidential text detection"
    )
    parser.add_argument("--data-path", default="dataset/ds.parquet")
    parser.add_argument("--output-dir", default="artifacts/bert_classifier")
    parser.add_argument("--model-name", default="xlm-roberta-base")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--train-batch-size", type=int, default=16)
    parser.add_argument("--eval-batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> TrainingConfig:
    base = TrainingConfig.default()
    return TrainingConfig(
        data_path=Path(args.data_path),
        output_dir=Path(args.output_dir),
        model_name=args.model_name,
        text_column=base.text_column,
        label_column=base.label_column,
        group_column=base.group_column,
        max_length=args.max_length,
        train_batch_size=args.train_batch_size,
        eval_batch_size=args.eval_batch_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        weight_decay=base.weight_decay,
        warmup_ratio=base.warmup_ratio,
        logging_steps=base.logging_steps,
        eval_steps=base.eval_steps,
        save_steps=base.save_steps,
        seed=args.seed,
        test_size=base.test_size,
        val_size=base.val_size,
    )


def pandas_to_hf(df: pd.DataFrame, text_column: str, label_column: str) -> Dataset:
    records = df[[text_column, label_column]].rename(columns={label_column: "labels"})
    return Dataset.from_pandas(records, preserve_index=False)


def tokenize_dataset(
    dataset: Dataset,
    tokenizer: AutoTokenizer,
    text_column: str,
    max_length: int,
) -> Dataset:
    def _tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        return dict(tokenizer(batch[text_column], truncation=True, max_length=max_length))

    return dataset.map(_tokenize, batched=True)


def save_metrics(metrics: dict[str, float], output_dir: Path, filename: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / filename
    target.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = build_config(args)

    set_seed(config.seed)
    dataset = load_dataset(str(config.data_path))
    splits = split_by_group(
        dataset=dataset,
        group_column=config.group_column,
        label_column=config.label_column,
        test_size=config.test_size,
        val_size=config.val_size,
        seed=config.seed,
    )

    tokenizer = AutoTokenizer.from_pretrained(config.model_name)
    model = AutoModelForSequenceClassification.from_pretrained(config.model_name, num_labels=2)

    train_dataset = tokenize_dataset(
        pandas_to_hf(splits.train, config.text_column, config.label_column),
        tokenizer,
        config.text_column,
        config.max_length,
    )
    val_dataset = tokenize_dataset(
        pandas_to_hf(splits.val, config.text_column, config.label_column),
        tokenizer,
        config.text_column,
        config.max_length,
    )
    test_dataset = tokenize_dataset(
        pandas_to_hf(splits.test, config.text_column, config.label_column),
        tokenizer,
        config.text_column,
        config.max_length,
    )

    training_args = TrainingArguments(
        output_dir=str(config.output_dir / "checkpoints"),
        overwrite_output_dir=True,
        num_train_epochs=config.epochs,
        learning_rate=config.learning_rate,
        per_device_train_batch_size=config.train_batch_size,
        per_device_eval_batch_size=config.eval_batch_size,
        weight_decay=config.weight_decay,
        warmup_ratio=config.warmup_ratio,
        evaluation_strategy="steps",
        save_strategy="steps",
        logging_strategy="steps",
        eval_steps=config.eval_steps,
        save_steps=config.save_steps,
        logging_steps=config.logging_steps,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        report_to=[],
        seed=config.seed,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=lambda pred: trainer_compute_metrics(
            (pred.predictions, np.asarray(pred.label_ids))
        ),
    )

    trainer.train()
    val_metrics = trainer.evaluate(eval_dataset=val_dataset)

    test_prediction: EvalPrediction = trainer.predict(test_dataset)
    test_probs = softmax_logits(np.asarray(test_prediction.predictions))[:, 1]
    test_labels = np.asarray(test_prediction.label_ids).astype(int)
    test_metrics = evaluate_classification(test_labels, test_probs, threshold=0.5)

    export_dir = config.output_dir / "model"
    trainer.save_model(str(export_dir))
    tokenizer.save_pretrained(str(export_dir))

    save_metrics(
        {k: float(v) for k, v in val_metrics.items() if isinstance(v, (float, int))},
        config.output_dir,
        "val_metrics.json",
    )
    save_metrics(test_metrics, config.output_dir, "test_metrics.json")
    upload_directory_if_configured(config.output_dir, os.environ.get("TRAIN_RESULTS_S3_URI_PREFIX"))


def softmax_logits(logits: NDArray[np.float64]) -> NDArray[np.float64]:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exp_values = np.exp(shifted)
    return np.asarray(exp_values / np.sum(exp_values, axis=1, keepdims=True), dtype=np.float64)


if __name__ == "__main__":
    main()
