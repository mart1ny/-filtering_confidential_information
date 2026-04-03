import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.storage.s3 import upload_directory_if_configured, upload_file_if_configured


def test_upload_file_if_configured_uploads_to_expected_s3_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    uploads: list[tuple[str, str, str]] = []
    file_path = tmp_path / "result.json"
    file_path.write_text("{}", encoding="utf-8")

    class FakeS3Client:
        def upload_file(self, local_path: str, bucket: str, key: str) -> None:
            uploads.append((local_path, bucket, key))

    fake_boto3 = ModuleType("boto3")
    fake_boto3.client = lambda *_args, **_kwargs: FakeS3Client()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.example.test")
    monkeypatch.setenv("AWS_REGION", "ru-1")

    upload_file_if_configured(file_path, "s3://bucket-name/results")

    assert uploads == [(str(file_path), "bucket-name", "results/result.json")]


def test_upload_file_if_configured_supports_single_slash_s3_uri(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    uploads: list[tuple[str, str, str]] = []
    file_path = tmp_path / "result.json"
    file_path.write_text("{}", encoding="utf-8")

    class FakeS3Client:
        def upload_file(self, local_path: str, bucket: str, key: str) -> None:
            uploads.append((local_path, bucket, key))

    fake_boto3 = ModuleType("boto3")
    fake_boto3.client = lambda *_args, **_kwargs: FakeS3Client()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    upload_file_if_configured(file_path, "s3:/bucket-name/results")

    assert uploads == [(str(file_path), "bucket-name", "results/result.json")]


def test_upload_directory_if_configured_uploads_all_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    uploads: list[tuple[str, str, str]] = []
    (tmp_path / "metrics").mkdir()
    (tmp_path / "metrics" / "val.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.bin").write_text("weights", encoding="utf-8")

    class FakeS3Client:
        def upload_file(self, local_path: str, bucket: str, key: str) -> None:
            uploads.append((local_path, bucket, key))

    fake_boto3 = ModuleType("boto3")
    fake_boto3.client = lambda *_args, **_kwargs: FakeS3Client()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    upload_directory_if_configured(tmp_path, "s3://bucket-name/training/run-1")

    assert uploads == [
        (str(tmp_path / "metrics" / "val.json"), "bucket-name", "training/run-1/metrics/val.json"),
        (str(tmp_path / "model.bin"), "bucket-name", "training/run-1/model.bin"),
    ]


def test_upload_file_if_configured_raises_for_invalid_uri(tmp_path: Path) -> None:
    file_path = tmp_path / "result.json"
    file_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid S3 URI"):
        upload_file_if_configured(file_path, "s3://")
