import builtins
import sys
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest

import app.training.data as training_data
from app.training.data import load_dataset, split_by_group


def test_split_by_group_has_no_leakage() -> None:
    frame = pd.DataFrame(
        {
            "id": [1, 1, 2, 2, 3, 3, 4, 4],
            "text": ["a", "b", "c", "d", "e", "f", "g", "h"],
            "is_contains_confidential": [0, 0, 1, 1, 0, 0, 1, 1],
        }
    )

    splits = split_by_group(
        dataset=frame,
        group_column="id",
        label_column="is_contains_confidential",
        test_size=0.25,
        val_size=0.25,
        seed=42,
    )

    train_ids = set(splits.train["id"].unique())
    val_ids = set(splits.val["id"].unique())
    test_ids = set(splits.test["id"].unique())

    assert not (train_ids & val_ids)
    assert not (train_ids & test_ids)
    assert not (val_ids & test_ids)


def test_load_dataset_drops_nulls_and_normalizes_types(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "text": ["hello", None, "123"],
            "source": ["s", "s", "s"],
            "conversation": ["c", "c", "c"],
            "prompt_lang": ["en", "en", "en"],
            "answer_lang": ["en", "en", "en"],
            "is_contains_confidential": [1.0, 0.0, 1.0],
        }
    )
    parquet_path = tmp_path / "dataset.parquet"
    frame.to_parquet(parquet_path)

    normalized = load_dataset(str(parquet_path))

    assert normalized.shape[0] == 2
    assert normalized["text"].tolist() == ["hello", "123"]
    assert normalized["is_contains_confidential"].tolist() == [1, 1]


def test_load_dataset_raises_on_missing_columns(tmp_path: Path) -> None:
    frame = pd.DataFrame({"id": [1], "text": ["hello"]})
    parquet_path = tmp_path / "dataset.parquet"
    frame.to_parquet(parquet_path)

    with pytest.raises(ValueError, match="missing required columns"):
        load_dataset(str(parquet_path))


def test_load_dataset_raises_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.parquet"
    with pytest.raises(FileNotFoundError, match="does not exist"):
        load_dataset(str(missing))


def test_load_dataset_from_s3_uri(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "source.parquet"
    frame = pd.DataFrame(
        {
            "id": [1],
            "text": ["hello"],
            "source": ["s"],
            "conversation": ["c"],
            "prompt_lang": ["en"],
            "answer_lang": ["en"],
            "is_contains_confidential": [1],
        }
    )
    frame.to_parquet(source)

    calls: dict[str, object] = {}

    class FakeS3Client:
        def download_file(self, bucket: str, key: str, target: str) -> None:
            calls["bucket"] = bucket
            calls["key"] = key
            Path(target).write_bytes(source.read_bytes())

    fake_boto3 = ModuleType("boto3")

    def _fake_client(service: str, **kwargs: object) -> FakeS3Client:
        calls["service"] = service
        calls["kwargs"] = kwargs
        return FakeS3Client()

    fake_boto3.client = _fake_client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.example.test")
    monkeypatch.setenv("AWS_REGION", "ru-1")

    loaded = load_dataset("s3://bucket-name/path/to/ds.parquet")

    assert loaded.shape[0] == 1
    assert calls["bucket"] == "bucket-name"
    assert calls["key"] == "path/to/ds.parquet"
    assert calls["service"] == "s3"
    assert calls["kwargs"] == {"endpoint_url": "https://s3.example.test", "region_name": "ru-1"}


def test_load_dataset_from_s3_single_slash_uri(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.parquet"
    frame = pd.DataFrame(
        {
            "id": [1],
            "text": ["hello"],
            "source": ["s"],
            "conversation": ["c"],
            "prompt_lang": ["en"],
            "answer_lang": ["en"],
            "is_contains_confidential": [1],
        }
    )
    frame.to_parquet(source)

    calls: dict[str, object] = {}

    class FakeS3Client:
        def download_file(self, bucket: str, key: str, target: str) -> None:
            calls["bucket"] = bucket
            calls["key"] = key
            Path(target).write_bytes(source.read_bytes())

    fake_boto3 = ModuleType("boto3")
    fake_boto3.client = lambda *_args, **_kwargs: FakeS3Client()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    loaded = load_dataset("s3:/bucket-name/path/to/ds.parquet")
    assert loaded.shape[0] == 1
    assert calls["bucket"] == "bucket-name"
    assert calls["key"] == "path/to/ds.parquet"


def test_load_dataset_from_s3_without_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "boto3", raising=False)
    real_import = builtins.__import__

    def _raising_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "boto3":
            raise ModuleNotFoundError("No module named 'boto3'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _raising_import)

    with pytest.raises(ModuleNotFoundError, match="boto3 is required"):
        load_dataset("s3://bucket/path/to/ds.parquet")


def test_load_dataset_from_s3_validates_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_boto3 = ModuleType("boto3")
    fake_boto3.client = lambda *_args, **_kwargs: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    with pytest.raises(ValueError, match="Invalid S3 dataset URI"):
        load_dataset("s3://bucket-without-key")


@pytest.mark.parametrize(
    ("test_size", "val_size", "message"),
    [
        (0.0, 0.2, "test_size must be in"),
        (0.2, 0.0, "val_size must be in"),
        (0.7, 0.3, "test_size \\+ val_size must be < 1"),
    ],
)
def test_split_by_group_validates_sizes(
    test_size: float,
    val_size: float,
    message: str,
) -> None:
    frame = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "text": ["a", "b", "c", "d"],
            "is_contains_confidential": [0, 1, 0, 1],
        }
    )

    with pytest.raises(ValueError, match=message):
        split_by_group(
            dataset=frame,
            group_column="id",
            label_column="is_contains_confidential",
            test_size=test_size,
            val_size=val_size,
            seed=42,
        )


def test_split_by_group_raises_on_leakage(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "text": ["a", "b", "c", "d"],
            "is_contains_confidential": [0, 1, 0, 1],
        }
    )

    class FakeGroupShuffleSplit:
        call_count = 0

        def __init__(self, *args: object, **kwargs: object) -> None:
            _ = (args, kwargs)

        def split(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            _ = (args, kwargs)
            if FakeGroupShuffleSplit.call_count == 0:
                FakeGroupShuffleSplit.call_count += 1
                yield [0, 1, 2], [3]
            else:
                yield [0, 1], [1, 2]

    monkeypatch.setattr(training_data, "GroupShuffleSplit", FakeGroupShuffleSplit)

    with pytest.raises(ValueError, match="Group split leakage detected"):
        split_by_group(
            dataset=frame,
            group_column="id",
            label_column="is_contains_confidential",
            test_size=0.25,
            val_size=0.25,
            seed=42,
        )
