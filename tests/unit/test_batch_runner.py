import sys
from pathlib import Path

from app.batch import runner


def test_runner_calls_compute_drift_metrics(monkeypatch, tmp_path: Path) -> None:
    called = {}

    def fake_compute_drift_metrics(run_date: str, output_dir: str) -> Path:
        called["run_date"] = run_date
        called["output_dir"] = output_dir
        return tmp_path / "drift.json"

    monkeypatch.setattr(runner, "compute_drift_metrics", fake_compute_drift_metrics)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner.py",
            "--run-date",
            "2026-03-01",
            "--output-dir",
            str(tmp_path),
        ],
    )

    runner.main()

    assert called["run_date"] == "2026-03-01"
    assert called["output_dir"] == str(tmp_path)
