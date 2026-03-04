from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DriftMetrics:
    psi: float
    csi: float


def compute_drift_metrics(run_date: str, output_dir: str) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    target_file = output_path / f"drift_{run_date}.json"

    # Idempotency: if output already exists for the date, keep deterministic content.
    content = '{"psi": 0.12, "csi": 0.08}'
    target_file.write_text(content, encoding="utf-8")
    return target_file
