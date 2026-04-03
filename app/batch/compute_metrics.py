from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from app.inference.store import AssessmentEventStore
from app.infrastructure.config.settings import settings
from app.storage.s3 import upload_file_if_configured


@dataclass(frozen=True)
class DriftMetrics:
    psi: float
    csi: float
    current_count: int
    baseline_count: int


def prepare_drift_output_dir(output_dir: str) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def compute_drift_metrics(run_date: str, output_dir: str) -> Path:
    output_path = prepare_drift_output_dir(output_dir)
    target_file = output_path / f"drift_{run_date}.json"

    metrics = _compute_metrics_for_day(_parse_run_date(run_date))
    content = json.dumps(asdict(metrics), ensure_ascii=True, sort_keys=True)
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


def _compute_metrics_for_day(target_day: date) -> DriftMetrics:
    store = _build_assessment_store()
    current_events = store.list_events_for_day(target_day)
    baseline_events = store.list_events_between(
        start=datetime.combine(target_day - timedelta(days=7), time.min, tzinfo=timezone.utc),
        end=datetime.combine(target_day, time.min, tzinfo=timezone.utc),
    )

    if not current_events or not baseline_events:
        return DriftMetrics(
            psi=0.0,
            csi=0.0,
            current_count=len(current_events),
            baseline_count=len(baseline_events),
        )

    psi = _population_stability_index(
        baseline=[event.risk_score for event in baseline_events],
        current=[event.risk_score for event in current_events],
        bins=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    )
    csi = _population_stability_index(
        baseline=[float(len(event.text)) for event in baseline_events],
        current=[float(len(event.text)) for event in current_events],
        bins=[0.0, 20.0, 50.0, 100.0, 200.0, math.inf],
    )
    return DriftMetrics(
        psi=round(psi, 4),
        csi=round(csi, 4),
        current_count=len(current_events),
        baseline_count=len(baseline_events),
    )


def _population_stability_index(
    baseline: list[float],
    current: list[float],
    bins: list[float],
) -> float:
    baseline_distribution = _bucket_distribution(baseline, bins)
    current_distribution = _bucket_distribution(current, bins)
    epsilon = 1e-6
    return sum(
        (current_bucket - baseline_bucket)
        * math.log((current_bucket + epsilon) / (baseline_bucket + epsilon))
        for baseline_bucket, current_bucket in zip(baseline_distribution, current_distribution)
    )


def _bucket_distribution(values: list[float], bins: list[float]) -> list[float]:
    if not values:
        return [0.0 for _ in range(len(bins) - 1)]

    counts = [0 for _ in range(len(bins) - 1)]
    for value in values:
        index = _resolve_bucket(value, bins)
        counts[index] += 1

    total = float(len(values))
    return [count / total for count in counts]


def _resolve_bucket(value: float, bins: list[float]) -> int:
    for index in range(len(bins) - 1):
        left = bins[index]
        right = bins[index + 1]
        if index == len(bins) - 2:
            if left <= value <= right:
                return index
        elif left <= value < right:
            return index
    return len(bins) - 2


def _build_assessment_store() -> AssessmentEventStore:
    return AssessmentEventStore(database_url=settings.resolved_review_database_url)


def _parse_run_date(raw_value: str) -> date:
    return date.fromisoformat(raw_value)
