import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.batch.compute_metrics import (
    compute_drift_metrics,
    prepare_drift_output_dir,
    publish_drift_metrics,
)


def test_compute_drift_metrics_is_idempotent(tmp_path: Path) -> None:
    first = compute_drift_metrics(run_date="2026-03-01", output_dir=str(tmp_path))
    second = compute_drift_metrics(run_date="2026-03-01", output_dir=str(tmp_path))

    assert first == second
    assert first.exists()
    assert first.read_text(encoding="utf-8") == '{"psi": 0.12, "csi": 0.08}'


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
