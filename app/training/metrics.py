from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score


@dataclass(frozen=True)
class ClassificationMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float


def evaluate_classification(
    y_true: NDArray[np.int_],
    y_prob: NDArray[np.float64],
    threshold: float = 0.5,
) -> dict[str, float]:
    y_pred = (y_prob >= threshold).astype(int)
    metrics = ClassificationMetrics(
        accuracy=float(accuracy_score(y_true, y_pred)),
        precision=float(precision_score(y_true, y_pred, zero_division=0)),
        recall=float(recall_score(y_true, y_pred, zero_division=0)),
        f1=float(f1_score(y_true, y_pred, zero_division=0)),
        roc_auc=float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else 0.0,
    )
    return {
        "accuracy": metrics.accuracy,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
        "roc_auc": metrics.roc_auc,
    }


def trainer_compute_metrics(
    eval_pred: tuple[NDArray[np.float64], NDArray[np.int_]],
) -> dict[str, float]:
    logits, labels = eval_pred
    probs = softmax(logits)[:, 1]
    return evaluate_classification(labels.astype(int), probs, threshold=0.5)


def softmax(logits: NDArray[np.float64]) -> NDArray[np.float64]:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exp_values = np.exp(shifted)
    return np.asarray(exp_values / np.sum(exp_values, axis=1, keepdims=True), dtype=np.float64)
