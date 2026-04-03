import json
import os
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

from app.batch.compute_metrics import (
    DriftMetrics,
    compute_drift_metrics,
    prepare_drift_output_dir,
    publish_drift_metrics,
)
from app.domain.models import Decision
from app.inference.store import AssessmentEvent


def test_compute_drift_metrics_is_idempotent(tmp_path: Path) -> None:
    class StubStore:
        def list_events_for_day(self, target_day: date) -> list[AssessmentEvent]:
            assert str(target_day) == "2026-03-01"
            return [
                AssessmentEvent(
                    event_id="cur-1",
                    text="passport 1234 567890",
                    risk_score=0.93,
                    decision=Decision.BLOCK,
                    reason="passport_pattern",
                    detector_used="hybrid",
                    created_at=datetime.now(timezone.utc),
                )
            ]

        def list_events_between(self, start, end) -> list[AssessmentEvent]:
            _ = (start, end)
            return [
                AssessmentEvent(
                    event_id="base-1",
                    text="hello",
                    risk_score=0.11,
                    decision=Decision.ALLOW,
                    reason="bert_risk_low",
                    detector_used="bert",
                    created_at=datetime.now(timezone.utc),
                ),
                AssessmentEvent(
                    event_id="base-2",
                    text="hello world",
                    risk_score=0.22,
                    decision=Decision.ALLOW,
                    reason="bert_risk_low",
                    detector_used="bert",
                    created_at=datetime.now(timezone.utc),
                ),
            ]

    import app.batch.compute_metrics as compute_module

    original_builder = compute_module._build_assessment_store
    compute_module._build_assessment_store = lambda: StubStore()  # type: ignore[assignment]
    try:
        first = compute_drift_metrics(run_date="2026-03-01", output_dir=str(tmp_path))
        second = compute_drift_metrics(run_date="2026-03-01", output_dir=str(tmp_path))
    finally:
        compute_module._build_assessment_store = original_builder  # type: ignore[assignment]

    assert first == second
    assert first.exists()
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["current_count"] == 1
    assert payload["baseline_count"] == 2
    assert payload["psi"] >= 0.0
    assert payload["csi"] >= 0.0


def test_compute_drift_metrics_returns_zero_when_no_source_data(tmp_path: Path) -> None:
    class EmptyStore:
        def list_events_for_day(self, target_day: date) -> list[AssessmentEvent]:
            _ = target_day
            return []

        def list_events_between(self, start, end) -> list[AssessmentEvent]:
            _ = (start, end)
            return []

    import app.batch.compute_metrics as compute_module

    original_builder = compute_module._build_assessment_store
    compute_module._build_assessment_store = lambda: EmptyStore()  # type: ignore[assignment]
    try:
        artifact = compute_drift_metrics(run_date="2026-03-01", output_dir=str(tmp_path))
    finally:
        compute_module._build_assessment_store = original_builder  # type: ignore[assignment]

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload == asdict(DriftMetrics(psi=0.0, csi=0.0, current_count=0, baseline_count=0))


def test_prepare_drift_output_dir_creates_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "nested" / "drift"

    created = prepare_drift_output_dir(str(output_dir))

    assert created == output_dir
    assert output_dir.exists()


def test_publish_drift_metrics_uploads_to_s3_when_configured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    uploads: list[tuple[str, str, str]] = []
    artifact = tmp_path / "drift_2026-03-02.json"
    artifact.write_text('{"psi": 0.12, "csi": 0.08}', encoding="utf-8")

    class FakeS3Client:
        def upload_file(self, local_path: str, bucket: str, key: str) -> None:
            uploads.append((local_path, bucket, key))

    fake_boto3 = ModuleType("boto3")
    fake_boto3.client = lambda *_args, **_kwargs: FakeS3Client()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setenv("DRIFT_RESULTS_S3_URI_PREFIX", "s3://bucket-name/drift-results")
    monkeypatch.setenv("AWS_REGION", "ru-1")

    uploaded = publish_drift_metrics(run_date="2026-03-02", output_dir=str(tmp_path))

    assert uploaded == artifact
    assert os.path.exists(uploads[0][0])
    assert uploads == [(str(artifact), "bucket-name", "drift-results/drift_2026-03-02.json")]


def test_publish_drift_metrics_raises_when_artifact_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Drift artifact does not exist"):
        publish_drift_metrics(run_date="2026-03-02", output_dir=str(tmp_path))
