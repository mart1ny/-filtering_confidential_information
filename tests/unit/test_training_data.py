from pathlib import Path

import pandas as pd
import pytest

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
