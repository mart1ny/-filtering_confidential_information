from __future__ import annotations

from dataclasses import dataclass

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
    dataset = pd.read_parquet(path)
    missing = REQUIRED_COLUMNS.difference(dataset.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    # Drop null text rows early to keep tokenizer pipeline deterministic.
    normalized = dataset.dropna(subset=["text", "is_contains_confidential", "id"]).copy()
    normalized["text"] = normalized["text"].astype(str)
    normalized["is_contains_confidential"] = normalized["is_contains_confidential"].astype(int)
    return normalized


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
