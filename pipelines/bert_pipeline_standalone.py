#!/usr/bin/env python3

# Colab-style BERT pipeline (single-file, notebook-friendly)
# Usage in Colab:
# 1) Upload ds.parquet to /content
# 2) Run:
#    !python /content/bert_pipeline_standalone.py

import json
import os
import random
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from tqdm import tqdm
from transformers import (
    DistilBertForSequenceClassification,
    DistilBertTokenizer,
    get_linear_schedule_with_warmup,
)

warnings.filterwarnings("ignore")

# =========================
# Config (edit in Colab)
# =========================
DATA_PATH = os.getenv("DATA_PATH", "/content/ds.parquet")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/content/artifacts/bert_classifier")
MODEL_NAME = os.getenv("MODEL_NAME", "distilbert-base-uncased")

MAX_LENGTH = int(os.getenv("MAX_LENGTH", "128"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "32"))
EPOCHS = int(os.getenv("EPOCHS", "3"))
LEARNING_RATE = float(os.getenv("LEARNING_RATE", "2e-5"))
WEIGHT_DECAY = float(os.getenv("WEIGHT_DECAY", "0.01"))
WARMUP_RATIO = float(os.getenv("WARMUP_RATIO", "0.1"))
RANDOM_STATE = int(os.getenv("SEED", "42"))
ACCUMULATION_STEPS = int(os.getenv("ACCUMULATION_STEPS", "2"))

TEXT_COLUMN = os.getenv("TEXT_COLUMN", "text")
LABEL_COLUMN = os.getenv("LABEL_COLUMN", "is_contains_confidential")
CONVERSATION_COLUMN = os.getenv("CONVERSATION_COLUMN", "conversation")


@dataclass
class Metrics:
    accuracy: float
    f1: float
    precision: float
    recall: float
    roc_auc: float


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_and_preprocess_data(file_path: str) -> pd.DataFrame:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset not found: {file_path}")

    df = pd.read_parquet(file_path)

    required_columns = {TEXT_COLUMN, LABEL_COLUMN}
    missing = required_columns.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    # Keep training deterministic and avoid NaNs in tokenizer/labels
    df = df.dropna(subset=[TEXT_COLUMN, LABEL_COLUMN]).copy()
    df = df.drop_duplicates(subset=[TEXT_COLUMN])

    if CONVERSATION_COLUMN in df.columns:
        df["combined_text"] = (
            df[TEXT_COLUMN].astype(str) + " " + df[CONVERSATION_COLUMN].fillna("").astype(str)
        )
    else:
        df["combined_text"] = df[TEXT_COLUMN].astype(str)

    df[LABEL_COLUMN] = df[LABEL_COLUMN].astype(int)

    class_counts = df[LABEL_COLUMN].value_counts().sort_index()
    print("Class distribution:")
    print(class_counts)

    return df


class ConfidentialDataset(Dataset):
    def __init__(self, dataframe: pd.DataFrame, tokenizer: DistilBertTokenizer, max_length: int):
        self.data = dataframe.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        text = str(self.data.iloc[idx]["combined_text"])
        label = int(self.data.iloc[idx][LABEL_COLUMN])

        encoding = self.tokenizer(
            text,
            add_special_tokens=True,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_attention_mask=True,
            return_tensors="pt",
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels": torch.tensor(label, dtype=torch.long),
        }


def build_weighted_sampler(train_df: pd.DataFrame) -> WeightedRandomSampler:
    class_counts = train_df[LABEL_COLUMN].value_counts().sort_index()
    class_weights = {cls: 1.0 / count for cls, count in class_counts.items()}
    sample_weights = train_df[LABEL_COLUMN].map(class_weights).to_numpy(dtype=np.float64)

    return WeightedRandomSampler(
        weights=torch.as_tensor(sample_weights, dtype=torch.double),
        num_samples=len(sample_weights),
        replacement=True,
    )


def compute_metrics(
    preds: list[int], labels: list[int], probs: list[float] | None = None
) -> Metrics:
    accuracy = float(accuracy_score(labels, preds))
    f1 = float(f1_score(labels, preds, zero_division=0))
    precision = float(precision_score(labels, preds, zero_division=0))
    recall = float(recall_score(labels, preds, zero_division=0))

    if probs is not None and len(set(labels)) > 1:
        roc_auc = float(roc_auc_score(labels, probs))
    else:
        roc_auc = 0.0

    return Metrics(
        accuracy=accuracy,
        f1=f1,
        precision=precision,
        recall=recall,
        roc_auc=roc_auc,
    )


def train_epoch(
    model: DistilBertForSequenceClassification,
    loader: DataLoader,
    optimizer: AdamW,
    scheduler,
    device: torch.device,
    scaler: torch.cuda.amp.GradScaler,
    accumulation_steps: int,
) -> float:
    model.train()
    total_loss = 0.0
    optimizer.zero_grad(set_to_none=True)

    progress = tqdm(loader, desc="Train", leave=False)
    for step, batch in enumerate(progress):
        input_ids = batch["input_ids"].to(device, non_blocking=True)
        attention_mask = batch["attention_mask"].to(device, non_blocking=True)
        labels = batch["labels"].to(device, non_blocking=True)

        with torch.cuda.amp.autocast(enabled=torch.cuda.is_available()):
            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss / accumulation_steps

        scaler.scale(loss).backward()

        if (step + 1) % accumulation_steps == 0:
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)

        total_loss += loss.item() * accumulation_steps
        progress.set_postfix({"loss": f"{loss.item() * accumulation_steps:.4f}"})

    # Flush trailing grads when loader size is not divisible by accumulation_steps
    if len(loader) % accumulation_steps != 0:
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()
        optimizer.zero_grad(set_to_none=True)

    return total_loss / max(len(loader), 1)


def evaluate(
    model: DistilBertForSequenceClassification,
    loader: DataLoader,
    device: torch.device,
) -> tuple[float, Metrics]:
    model.eval()

    total_loss = 0.0
    preds: list[int] = []
    labels_all: list[int] = []
    probs_pos: list[float] = []

    with torch.no_grad():
        for batch in tqdm(loader, desc="Eval", leave=False):
            input_ids = batch["input_ids"].to(device, non_blocking=True)
            attention_mask = batch["attention_mask"].to(device, non_blocking=True)
            labels = batch["labels"].to(device, non_blocking=True)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            total_loss += float(outputs.loss.item())

            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=1)[:, 1]
            batch_preds = torch.argmax(logits, dim=1)

            preds.extend(batch_preds.detach().cpu().tolist())
            labels_all.extend(labels.detach().cpu().tolist())
            probs_pos.extend(probabilities.detach().cpu().tolist())

    metrics = compute_metrics(preds, labels_all, probs_pos)
    avg_loss = total_loss / max(len(loader), 1)
    return avg_loss, metrics


def save_metrics(metrics: Metrics, path: str) -> None:
    payload = {
        "accuracy": metrics.accuracy,
        "f1": metrics.f1,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "roc_auc": metrics.roc_auc,
    }
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    set_seed(RANDOM_STATE)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    df = load_and_preprocess_data(DATA_PATH)

    train_df, temp_df = train_test_split(
        df,
        test_size=0.3,
        stratify=df[LABEL_COLUMN],
        random_state=RANDOM_STATE,
    )
    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.5,
        stratify=temp_df[LABEL_COLUMN],
        random_state=RANDOM_STATE,
    )

    tokenizer = DistilBertTokenizer.from_pretrained(MODEL_NAME)

    train_dataset = ConfidentialDataset(train_df, tokenizer, MAX_LENGTH)
    val_dataset = ConfidentialDataset(val_df, tokenizer, MAX_LENGTH)
    test_dataset = ConfidentialDataset(test_df, tokenizer, MAX_LENGTH)

    sampler = build_weighted_sampler(train_df)

    num_workers = 2 if torch.cuda.is_available() else 0
    train_loader = DataLoader(
        train_dataset,
        sampler=sampler,
        batch_size=BATCH_SIZE,
        pin_memory=torch.cuda.is_available(),
        num_workers=num_workers,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        pin_memory=torch.cuda.is_available(),
        num_workers=num_workers,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        pin_memory=torch.cuda.is_available(),
        num_workers=num_workers,
    )

    model = DistilBertForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
    model.to(device)

    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    total_steps = max(len(train_loader) * EPOCHS // ACCUMULATION_STEPS, 1)
    warmup_steps = int(total_steps * WARMUP_RATIO)
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )
    scaler = torch.cuda.amp.GradScaler(enabled=torch.cuda.is_available())

    best_val_f1 = -1.0
    best_model_path = os.path.join(OUTPUT_DIR, "best_model.pth")

    for epoch in range(EPOCHS):
        train_loss = train_epoch(
            model=model,
            loader=train_loader,
            optimizer=optimizer,
            scheduler=scheduler,
            device=device,
            scaler=scaler,
            accumulation_steps=ACCUMULATION_STEPS,
        )

        val_loss, val_metrics = evaluate(model, val_loader, device)

        print(f"\nEpoch {epoch + 1}/{EPOCHS}")
        print(f"Train loss: {train_loss:.4f}")
        print(f"Val loss: {val_loss:.4f}")
        print(f"Val accuracy: {val_metrics.accuracy:.4f}")
        print(f"Val f1: {val_metrics.f1:.4f}")

        if val_metrics.f1 > best_val_f1:
            best_val_f1 = val_metrics.f1
            torch.save(model.state_dict(), best_model_path)
            print("Saved new best model")

    # Test on best checkpoint
    model.load_state_dict(torch.load(best_model_path, map_location=device))
    test_loss, test_metrics = evaluate(model, test_loader, device)

    print("\nTest results")
    print(f"Test loss: {test_loss:.4f}")
    print(f"Test accuracy: {test_metrics.accuracy:.4f}")
    print(f"Test f1: {test_metrics.f1:.4f}")
    print(f"Test precision: {test_metrics.precision:.4f}")
    print(f"Test recall: {test_metrics.recall:.4f}")
    print(f"Test roc_auc: {test_metrics.roc_auc:.4f}")

    # Save final artifacts
    model_dir = os.path.join(OUTPUT_DIR, "model")
    os.makedirs(model_dir, exist_ok=True)
    model.save_pretrained(model_dir)
    tokenizer.save_pretrained(model_dir)

    save_metrics(val_metrics, os.path.join(OUTPUT_DIR, "val_metrics.json"))
    save_metrics(test_metrics, os.path.join(OUTPUT_DIR, "test_metrics.json"))

    print(f"\nArtifacts saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
