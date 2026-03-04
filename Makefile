.PHONY: sync run test lint format docker-build docker-up train-bert train-bert-remote

sync:
	uv sync --all-groups

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest

lint:
	uv run black --check .
	uv run isort --check-only .
	uv run flake8 app tests dags
	uv run pylint app tests dags
	uv run mypy

format:
	uv run black .
	uv run isort .

docker-build:
	docker build -t confidential-filter-service:local .

docker-up:
	docker compose up -d --build

train-bert:
	uv run --extra train python -m app.training.train_bert --data-path dataset/ds.parquet --output-dir artifacts/bert_classifier

train-bert-remote:
	./pipelines/train_bert_remote.sh
