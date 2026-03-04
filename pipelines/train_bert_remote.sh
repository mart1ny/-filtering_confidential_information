#!/usr/bin/env bash
set -euo pipefail

# Standalone remote pipeline for BERT training.
# Run from repository root.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DATA_PATH="${DATA_PATH:-dataset/ds.parquet}"
OUTPUT_DIR="${OUTPUT_DIR:-artifacts/bert_classifier}"
MODEL_NAME="${MODEL_NAME:-xlm-roberta-base}"
EPOCHS="${EPOCHS:-2}"
TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-16}"
EVAL_BATCH_SIZE="${EVAL_BATCH_SIZE:-32}"
LEARNING_RATE="${LEARNING_RATE:-2e-5}"
MAX_LENGTH="${MAX_LENGTH:-256}"
SEED="${SEED:-42}"
VENV_DIR="${VENV_DIR:-.venv_train}"

if [[ ! -f "$DATA_PATH" ]]; then
  echo "[ERROR] Dataset not found: $DATA_PATH"
  exit 1
fi

if command -v uv >/dev/null 2>&1; then
  echo "[INFO] Using uv to prepare environment"
  uv sync --all-groups --extra train
  RUNNER=(uv run --extra train)
else
  echo "[INFO] uv not found, fallback to venv + pip"
  python3 -m venv "$VENV_DIR"
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
  python -m pip install --upgrade pip
  python -m pip install \
    fastapi==0.115.6 \
    uvicorn==0.32.1 \
    pydantic==2.10.3 \
    pydantic-settings==2.7.0 \
    prometheus-client==0.21.1 \
    python-dotenv==1.0.1 \
    pandas==2.2.3 \
    pyarrow==18.1.0 \
    scikit-learn==1.6.0 \
    numpy==2.2.1 \
    torch==2.5.1 \
    transformers==4.47.1 \
    datasets==3.2.0 \
    accelerate==1.2.1
  RUNNER=(python)
fi

mkdir -p "$OUTPUT_DIR"

echo "[INFO] Starting BERT training"
"${RUNNER[@]}" -m app.training.train_bert \
  --data-path "$DATA_PATH" \
  --output-dir "$OUTPUT_DIR" \
  --model-name "$MODEL_NAME" \
  --epochs "$EPOCHS" \
  --train-batch-size "$TRAIN_BATCH_SIZE" \
  --eval-batch-size "$EVAL_BATCH_SIZE" \
  --learning-rate "$LEARNING_RATE" \
  --max-length "$MAX_LENGTH" \
  --seed "$SEED"

echo "[INFO] Training complete"
echo "[INFO] Model artifacts: $OUTPUT_DIR/model"
echo "[INFO] Validation metrics: $OUTPUT_DIR/val_metrics.json"
echo "[INFO] Test metrics: $OUTPUT_DIR/test_metrics.json"
