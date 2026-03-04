import numpy as np

from app.training.metrics import evaluate_classification, softmax


def test_softmax_rows_sum_to_one() -> None:
    logits = np.array([[1.0, 2.0], [3.0, 4.0]])
    probs = softmax(logits)
    np.testing.assert_allclose(np.sum(probs, axis=1), np.array([1.0, 1.0]))


def test_evaluate_classification_outputs_required_metrics() -> None:
    y_true = np.array([0, 1, 1, 0])
    y_prob = np.array([0.1, 0.9, 0.7, 0.2])

    metrics = evaluate_classification(y_true, y_prob, threshold=0.5)

    assert set(metrics.keys()) == {"accuracy", "precision", "recall", "f1", "roc_auc"}
    assert metrics["f1"] > 0.0
