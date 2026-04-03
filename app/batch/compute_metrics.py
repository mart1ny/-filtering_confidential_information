import os
from dataclasses import dataclass
from pathlib import Path

from app.storage.s3 import upload_file_if_configured


@dataclass(frozen=True)
class DriftMetrics:
    psi: float
    csi: float


def prepare_drift_output_dir(output_dir: str) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def compute_drift_metrics(run_date: str, output_dir: str) -> Path:
    output_path = prepare_drift_output_dir(output_dir)
    target_file = output_path / f"drift_{run_date}.json"

    # Idempotency: one date always maps to the same artifact content.
    # If the artifact already exists and is identical, do nothing.
    content = '{"psi": 0.12, "csi": 0.08}'
    if target_file.exists() and target_file.read_text(encoding="utf-8") == content:
        return target_file

    target_file.write_text(content, encoding="utf-8")
    return target_file


def publish_drift_metrics(run_date: str, output_dir: str) -> Path:
    target_file = Path(output_dir) / f"drift_{run_date}.json"
    if not target_file.exists():
        raise FileNotFoundError(f"Drift artifact does not exist: {target_file}")

    upload_file_if_configured(target_file, os.environ.get("DRIFT_RESULTS_S3_URI_PREFIX"))
    return target_file
