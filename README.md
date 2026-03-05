# Confidential Information Filter

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-online%20service-009688.svg)](#)
[![Airflow](https://img.shields.io/badge/Airflow-batch%20pipeline-017CEE.svg)](#)
[![BERT](https://img.shields.io/badge/ML-BERT%20training-orange.svg)](#)
[![Architecture](https://img.shields.io/badge/architecture-Clean%20Architecture-black.svg)](#)

Интеллектуальная система фильтрации конфиденциальной информации в онлайн- и batch-режимах.

## TL;DR

- Что решает: предотвращает утечки чувствительных данных до отправки во внешние каналы.
- Как работает: `rules + ML` -> решение `allow/review/block`.
- Что уже есть: REST API, Airflow DAG, BERT pipeline, CI/CD, мониторинг-конфиги.
- Где смотреть статус по требованиям: [Implementation Status](docs/IMPLEMENTATION_STATUS.md).

## Demo Flow

1. Пользователь отправляет текст/файл.
2. Сервис проверяет контент правилами и моделью.
3. Возвращает решение и пишет технический аудит.
4. Batch слой считает drift/качество и публикует метрики.

## Реализованные этапы

- Этап 1: каркас проекта, Clean Architecture, quality tooling.
- Этап 2: online REST-сервис + Docker + CI/CD.
- Этап 3: batch-сервис (Airflow) + pipeline обучения BERT.

Подробная матрица: [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)

## Состав репозитория

```text
app/
  domain/            # доменные модели и интерфейсы
  application/       # use cases
  adapters/          # правила детекции и адаптеры
  infrastructure/    # конфиги, метрики, техслой
  api/               # FastAPI endpoints
  batch/             # batch-вычисления
  training/          # обучение BERT

configs/             # конфиги обучения
dags/                # Airflow DAGs
tests/               # unit + integration
docs/                # ADR, C4, статус реализации
pipelines/           # standalone scripts (remote/colab)
infra/               # Prometheus/Grafana/Alertmanager
```

## REST API

- `GET /health` — healthcheck
- `POST /v1/assess` — оценка текста (`allow/review/block`)
- `POST /v1/metrics/drift` — прием PSI/CSI
- `GET /metrics` — Prometheus endpoint

Swagger:
- `http://localhost:8000/docs`
- `http://localhost:8000/openapi.json`

## Быстрый старт

### 1. Установка

```bash
cp .env.example .env
uv sync --all-groups
```

### 2. Запуск API

```bash
make run
```

### 3. Проверка качества

```bash
make lint
make test
```

### 4. Локальный docker-stack

```bash
make docker-build
make docker-up
```

## Обучение модели

### Внутри проекта

```bash
make train-bert
```

### На удаленном сервере

```bash
./pipelines/train_bert_remote.sh
```

### В Google Colab

```bash
!python /content/bert_pipeline_standalone.py
```

Файл: `pipelines/bert_pipeline_standalone.py`

## Batch (Airflow)

- Drift DAG: `dags/confidential_batch_dag.py`
- Training DAG: `dags/bert_training_dag.py`

Backfill пример:

```bash
airflow dags backfill confidential_metrics_batch -s 2026-02-01 -e 2026-02-07
```

## CI/CD

Workflow: `.github/workflows/ci-cd.yml`

Pipeline шаги:
1. Установка зависимостей
2. Линтеры (`black`, `isort`, `flake8`, `pylint`, `mypy`)
3. Тесты
4. Сборка контейнера
5. Публикация образа
6. Деплой на удаленный сервер

## Наблюдаемость

- Prometheus: `infra/prometheus/prometheus.yml`
- Grafana dashboard: `infra/grafana/dashboards/confidential-overview.json`
- Alertmanager: `infra/alertmanager.yml`

## Документация архитектуры

- ADR (online): `docs/adr/ADR-001-online-service.md`
- ADR (batch): `docs/adr/ADR-002-batch-service.md`
- C4: `docs/architecture/c4-container.puml`

## Roadmap

- Подтвердить quality gate в целевом окружении с финальным coverage-отчетом.
- Довести продовые секреты и деплой-процедуру до полноценного runbook.
- Расширить MLOps: registry, versioning, controlled retrain.

## Contribution

См. [CONTRIBUTING.md](CONTRIBUTING.md)
