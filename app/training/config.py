from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainingConfig:
    data_path: Path
    output_dir: Path
    model_name: str
    text_column: str
    label_column: str
    group_column: str
    max_length: int
    train_batch_size: int
    eval_batch_size: int
    epochs: int
    learning_rate: float
    weight_decay: float
    warmup_ratio: float
    logging_steps: int
    eval_steps: int
    save_steps: int
    seed: int
    test_size: float
    val_size: float

    @staticmethod
    def default() -> "TrainingConfig":
        return TrainingConfig(
            data_path=Path("dataset/ds.parquet"),
            output_dir=Path("artifacts/bert_classifier"),
            model_name="xlm-roberta-base",
            text_column="text",
            label_column="is_contains_confidential",
            group_column="id",
            max_length=256,
            train_batch_size=16,
            eval_batch_size=32,
            epochs=2,
            learning_rate=2e-5,
            weight_decay=0.01,
            warmup_ratio=0.1,
            logging_steps=50,
            eval_steps=200,
            save_steps=200,
            seed=42,
            test_size=0.15,
            val_size=0.15,
        )
