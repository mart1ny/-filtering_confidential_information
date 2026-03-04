# Confidential Filter Service

ML-assisted platform for filtering confidential information in online (REST) and batch (Airflow) modes.

## Project Status Checklist

### 1. Repository and code quality
- [x] Git repository with commit history
- [x] Clean Architecture layout
- [x] Unit tests with coverage target `>70%`
- [x] Clear README with run, reproduce, and deploy steps

### 2. Service packaging and delivery
- [x] Pinned dependencies via `uv` (`pyproject.toml` + `uv.lock`)
- [x] Dockerfile for service image build
- [x] CI/CD pipeline with push-based deployment to remote server
- [x] Image push to container registry (GHCR in workflow)
- [x] Mandatory linters in pipeline: `flake8`, `isort`, `pylint`, `mypy`, `black`
- [x] Secrets through `.env` and CI/CD secret store

### 3. Batch service
- [x] Airflow DAG based on project code
- [x] `DockerOperator` used in DAG
- [x] Idempotency ensured by deterministic run-date artifact
- [x] Backfill procedure documented
- [x] BERT training DAG pipeline included

### 4. REST service
- [x] At least 3 endpoints
- [x] Healthcheck endpoint
- [x] OpenAPI/Swagger docs available

### 5. Monitoring and alerting
- [x] Prometheus metrics endpoint
- [x] Grafana dashboard config included
- [x] Alerting config for email/Telegram included
- [x] ML metrics include quality counters and PSI/CSI buckets

### 6. Architecture documentation
- [x] ADR for online service
- [x] ADR for batch service
- [x] C4 container diagram source

## Clean Architecture Structure

```text
app/
  domain/            # Core models and interfaces
  application/       # Use cases
  adapters/          # Concrete detector implementations
  infrastructure/    # Config, monitoring, technical concerns
  api/               # FastAPI transport layer
  batch/             # Batch metric computation
dags/                # Airflow DAG definitions
tests/               # Unit and integration tests
docs/adr/            # Architecture Decision Records
docs/architecture/   # C4 diagram source
infra/               # Prometheus/Grafana/Alertmanager configs
```

## API Endpoints

- `GET /health` - service health status
- `POST /v1/assess` - evaluate text and return `allow/review/block`
- `POST /v1/metrics/drift` - ingest PSI/CSI metrics
- `GET /metrics` - Prometheus metrics

Swagger UI: `http://localhost:8000/docs`
OpenAPI JSON: `http://localhost:8000/openapi.json`

## Local Run

### Prerequisites
- Python 3.11+
- `uv`
- Docker and Docker Compose

### Setup

```bash
cp .env.example .env
uv sync --all-groups
```

### Run service

```bash
make run
```

### Run tests and coverage

```bash
make test
```

### Run linters

```bash
make lint
```

### Format code

```bash
make format
```

## Docker

Build image:

```bash
make docker-build
```

Run local stack (app + prometheus + grafana):

```bash
make docker-up
```

## CI/CD (Push Deploy Model)

Workflow file: `.github/workflows/ci-cd.yml`

Pipeline stages:
1. Install deps with `uv`.
2. Run `black --check`, `isort --check-only`, `flake8`, `pylint`, `mypy`.
3. Run tests with coverage gate.
4. Build Docker image.
5. Push image to GHCR.
6. SSH deploy on remote host with `docker pull` + `docker compose up -d`.

Required repository secrets:
- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- Optional SMTP/Telegram secrets for alerting

## Environment and Secrets

- Local config from `.env`
- Commit-safe template in `.env.example`
- CI/CD and production secrets must be stored in secure secret manager (GitHub/GitLab secrets, Vault, cloud secret store)

## Airflow Batch Service

DAG file: `dags/confidential_batch_dag.py`

Task:
- Runs containerized batch job via `DockerOperator`
- Job command: `python -m app.batch.runner --run-date {{ ds }} --output-dir /opt/airflow/data/drift`

Idempotency approach:
- Output artifact path is deterministic: `drift_<run_date>.json`
- Re-run for same date rewrites deterministic content (no duplication)

Backfill example:

```bash
airflow dags backfill confidential_metrics_batch -s 2026-02-01 -e 2026-02-07
```

## BERT Training Pipeline

Training module:
- `app/training/train_bert.py` - end-to-end training pipeline for BERT-like classifier
- `app/training/data.py` - data loading and leakage-safe split by `id`
- `app/training/metrics.py` - offline quality metrics

Run training locally:

```bash
make train-bert
```

Run training on another server with standalone pipeline script:

```bash
./pipelines/train_bert_remote.sh
```

Example with custom params:

```bash
DATA_PATH=/data/ds.parquet OUTPUT_DIR=/srv/artifacts/bert MODEL_NAME=xlm-roberta-base EPOCHS=3 ./pipelines/train_bert_remote.sh
```

Direct command:

```bash
uv run --extra train python -m app.training.train_bert \
  --data-path dataset/ds.parquet \
  --output-dir artifacts/bert_classifier \
  --model-name xlm-roberta-base
```

Output artifacts:
- `artifacts/bert_classifier/model/` - tokenizer + fine-tuned model
- `artifacts/bert_classifier/val_metrics.json`
- `artifacts/bert_classifier/test_metrics.json`

Airflow training DAG:
- `dags/bert_training_dag.py`
- DAG id: `bert_training_pipeline`

## Monitoring and Alerting

- Prometheus scrape config: `infra/prometheus/prometheus.yml`
- Grafana dashboard: `infra/grafana/dashboards/confidential-overview.json`
- Alertmanager receivers (email + telegram): `infra/alertmanager.yml`
- ML drift metrics:
  - PSI bucket counter
  - CSI bucket counter
  - Request and latency metrics

## Architecture Documentation

- ADR online: `docs/adr/ADR-001-online-service.md`
- ADR batch: `docs/adr/ADR-002-batch-service.md`
- C4 source: `docs/architecture/c4-container.puml`

## Reproducibility Steps

1. `cp .env.example .env`
2. `uv sync --all-groups`
3. `make lint`
4. `make test`
5. `make run`
6. Open Swagger at `http://localhost:8000/docs`

## Deployment Steps

1. Push to `main` branch.
2. CI builds, validates, and publishes image.
3. CD job connects to server over SSH.
4. Server pulls latest image and restarts service.
