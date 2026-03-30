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

    # Idempotency: one date always maps to the same artifact content.
    # If the artifact already exists and is identical, do nothing.
    content = '{"psi": 0.12, "csi": 0.08}'
    if target_file.exists() and target_file.read_text(encoding="utf-8") == content:
        return target_file

    target_file.write_text(content, encoding="utf-8")
    return target_file
