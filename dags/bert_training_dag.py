from datetime import datetime

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator

with DAG(
    dag_id="bert_training_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="@weekly",
    catchup=False,
    max_active_runs=1,
    tags=["ml", "training", "bert"],
) as dag:
    train_model = DockerOperator(
        task_id="train_bert_classifier",
        image="ghcr.io/your-org/confidential-filter-service:latest",
        api_version="auto",
        auto_remove="force",
        command=(
            "uv run --extra train python -m app.training.train_bert "
            "--data-path dataset/ds.parquet "
            "--output-dir artifacts/bert_classifier"
        ),
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        mount_tmp_dir=False,
        environment={
            "APP_ENV": "training",
        },
    )

    train_model
