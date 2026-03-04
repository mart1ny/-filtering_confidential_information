import pandas as pd

from app.training.data import split_by_group


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
