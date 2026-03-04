# Система фильтрации конфиденциальной информации

Сервис для автоматической проверки текста и файлов перед отправкой во внешние каналы (LLM-чат, CRM, почта и т.д.).

Проект сочетает:
- онлайн-проверку (REST API),
- batch-процессы (Airflow),
- ML-пайплайн обучения BERT,
- наблюдаемость (Prometheus/Grafana) и базовый CI/CD.

## Что это за проект

Цель проекта: снижать риск утечки чувствительных данных за счет автоматической классификации контента и политик решений `allow/review/block`.

MVP-идея:
- правила ловят критичные паттерны (карты/паспорта/токены),
- ML-модель помогает в неочевидных кейсах,
- решение логируется и наблюдается через метрики.

## Что уже реализовано

### Этап 1. Каркас и инженерная база
- Репозиторий с историей коммитов.
- Структура в стиле Clean Architecture.
- `pyproject.toml` с pinned зависимостями.
- Базовые команды в `Makefile`.
- Шаблон переменных окружения `.env.example`.

### Этап 2. Онлайн-сервис
- FastAPI-сервис с эндпоинтами:
  - `GET /health`
  - `POST /v1/assess`
  - `POST /v1/metrics/drift`
  - `GET /metrics`
- OpenAPI/Swagger: `/docs`, `/openapi.json`.
- Dockerfile и `docker-compose` для локального запуска.
- CI/CD workflow с линтерами, тестами, сборкой и деплоем.

### Этап 3. Batch и ML-пайплайн
- Airflow DAG для batch-метрик на `DockerOperator`.
- Airflow DAG для обучения модели.
- Модуль обучения BERT в проекте (`app/training`).
- Standalone-скрипт под Google Colab и отдельный remote-скрипт.
- Сохранение артефактов модели и метрик (`val/test`).

## Текущий результат обучения модели

Папка артефактов: `bert_classifier/`

Текущие метрики (последний запуск):
- Validation F1: `0.6159`
- Test F1: `0.6393`
- Test ROC-AUC: `0.8317`

## Архитектура проекта

```text
app/
  domain/            # доменные модели и интерфейсы
  application/       # use cases
  adapters/          # реализации детекторов
  infrastructure/    # конфиги, метрики, тех. слой
  api/               # транспортный слой (FastAPI)
  batch/             # batch-вычисления
  training/          # обучение BERT

configs/             # конфиги обучения
dags/                # Airflow DAGs
tests/               # unit + integration
pipelines/           # standalone/remote pipeline scripts
infra/               # Prometheus/Grafana/Alertmanager
```

## Быстрый старт (локально)

### 1) Подготовка
```bash
cp .env.example .env
uv sync --all-groups
```

### 2) Запуск API
```bash
make run
```

### 3) Проверка качества кода
```bash
make lint
make test
```

## Запуск обучения BERT

### Внутри проекта
```bash
make train-bert
```

### На другом сервере
```bash
./pipelines/train_bert_remote.sh
```

### В Google Colab
Используйте standalone-файл:
- `pipelines/bert_pipeline_standalone.py`

Пример запуска в Colab:
```bash
!python /content/bert_pipeline_standalone.py
```

С кастомными путями:
```bash
!DATA_PATH=/content/ds.parquet OUTPUT_DIR=/content/bert_classifier python /content/bert_pipeline_standalone.py
```

## Batch-процессы

- DAG drift-метрик: `dags/confidential_batch_dag.py`
- DAG обучения: `dags/bert_training_dag.py`

Backfill пример:
```bash
airflow dags backfill confidential_metrics_batch -s 2026-02-01 -e 2026-02-07
```

## CI/CD

Workflow: `.github/workflows/ci-cd.yml`

Что делает pipeline:
1. Устанавливает зависимости.
2. Гоняет `black`, `isort`, `flake8`, `pylint`, `mypy`.
3. Запускает тесты.
4. Собирает Docker-образ.
5. Пушит образ в registry.
6. Выполняет деплой на удаленный сервер по SSH.

## Наблюдаемость

- Метрики приложения: `/metrics`
- Prometheus конфиг: `infra/prometheus/prometheus.yml`
- Grafana dashboard: `infra/grafana/dashboards/confidential-overview.json`
- Alertmanager: `infra/alertmanager.yml`

## Документация по архитектуре

- ADR online: `docs/adr/ADR-001-online-service.md`
- ADR batch: `docs/adr/ADR-002-batch-service.md`
- C4: `docs/architecture/c4-container.puml`

## Что осталось до полного production-ready

- Прогнать полный quality gate в целевом окружении (`lint/test/coverage`) и зафиксировать отчет.
- Довести CI/CD на реальном удаленном сервере с прод-секретами.
- Уточнить пороги классификации и policy-логику на пилотной обратной связи.
- Расширить MLOps-часть (версионирование моделей, registry, ретрейн-процедуры).
