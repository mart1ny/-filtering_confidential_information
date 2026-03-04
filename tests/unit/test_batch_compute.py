from pathlib import Path

from app.batch.compute_metrics import compute_drift_metrics


def test_compute_drift_metrics_is_idempotent(tmp_path: Path) -> None:
    first = compute_drift_metrics(run_date="2026-03-01", output_dir=str(tmp_path))
    second = compute_drift_metrics(run_date="2026-03-01", output_dir=str(tmp_path))

    assert first == second
    assert first.exists()
    assert first.read_text(encoding="utf-8") == '{"psi": 0.12, "csi": 0.08}'
