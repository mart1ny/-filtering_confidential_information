from datetime import datetime

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator

with DAG(
    dag_id="confidential_metrics_batch",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=True,
    max_active_runs=1,
    tags=["ml", "drift", "idempotent"],
) as dag:
    compute_drift = DockerOperator(
        task_id="compute_drift",
        image="ghcr.io/your-org/confidential-filter-service:latest",
        api_version="auto",
        auto_remove=True,
        command=(
            "python -m app.batch.runner "
            "--run-date {{ ds }} "
            "--output-dir /opt/airflow/data/drift"
        ),
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        mount_tmp_dir=False,
        environment={
            "APP_ENV": "batch",
        },
    )

    compute_drift
