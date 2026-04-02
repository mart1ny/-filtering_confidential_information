from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


@dataclass(frozen=True)
class DatasetSplits:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame


REQUIRED_COLUMNS = {
    "id",
    "text",
    "source",
    "conversation",
    "prompt_lang",
    "answer_lang",
    "is_contains_confidential",
}


def load_dataset(path: str) -> pd.DataFrame:
    dataset = pd.read_parquet(_resolve_dataset_path(path))
    missing = REQUIRED_COLUMNS.difference(dataset.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    # Drop null text rows early to keep tokenizer pipeline deterministic.
    normalized = dataset.dropna(subset=["text", "is_contains_confidential", "id"]).copy()
    normalized["text"] = normalized["text"].astype(str)
    normalized["is_contains_confidential"] = normalized["is_contains_confidential"].astype(int)
    return normalized


def _resolve_dataset_path(path: str) -> str:
    if path.startswith("s3://"):
        return _download_from_s3(path)

    local_path = Path(path)
    if not local_path.exists():
        raise FileNotFoundError(f"Dataset file does not exist: {path}")
    return str(local_path)


def _download_from_s3(uri: str) -> str:
    try:
        import boto3
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "boto3 is required to load dataset from S3 URI. "
            "Install training dependencies (`uv sync --extra train`)."
        ) from exc

    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 dataset URI: {uri}")

    with NamedTemporaryFile(prefix="train_dataset_", suffix=".parquet", delete=False) as tmp_file:
        local_path = tmp_file.name

    endpoint_url = os.environ.get("S3_ENDPOINT_URL")
    region_name = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    client_kwargs = {}
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
    if region_name:
        client_kwargs["region_name"] = region_name

    s3 = boto3.client("s3", **client_kwargs)
    s3.download_file(bucket, key, local_path)
    return local_path


def split_by_group(
    dataset: pd.DataFrame,
    group_column: str,
    label_column: str,
    test_size: float,
    val_size: float,
    seed: int,
) -> DatasetSplits:
    if not 0 < test_size < 1:
        raise ValueError("test_size must be in (0,1)")
    if not 0 < val_size < 1:
        raise ValueError("val_size must be in (0,1)")
    if test_size + val_size >= 1:
        raise ValueError("test_size + val_size must be < 1")

    splitter_outer = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    outer_train_idx, test_idx = next(
        splitter_outer.split(dataset, dataset[label_column], groups=dataset[group_column])
    )

    train_val = dataset.iloc[outer_train_idx].reset_index(drop=True)
    test = dataset.iloc[test_idx].reset_index(drop=True)

    inner_val_size = val_size / (1 - test_size)
    splitter_inner = GroupShuffleSplit(n_splits=1, test_size=inner_val_size, random_state=seed)
    train_idx, val_idx = next(
        splitter_inner.split(train_val, train_val[label_column], groups=train_val[group_column])
    )

    train = train_val.iloc[train_idx].reset_index(drop=True)
    val = train_val.iloc[val_idx].reset_index(drop=True)

    # Ensure there is no conversation leakage by checking group overlap.
    train_groups = set(train[group_column].unique())
    val_groups = set(val[group_column].unique())
    test_groups = set(test[group_column].unique())
    if train_groups & val_groups or train_groups & test_groups or val_groups & test_groups:
        raise ValueError("Group split leakage detected")

    return DatasetSplits(train=train, val=val, test=test)
