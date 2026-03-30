import os
from datetime import datetime

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

with DAG(
    dag_id="confidential_metrics_batch",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=True,
    max_active_runs=1,
    tags=["ml", "drift", "idempotent"],
) as dag:
    app_image = os.environ.get("APP_IMAGE", "confidential-filter-service:local")

    compute_drift = DockerOperator(
        task_id="compute_drift",
        image=app_image,
        api_version="auto",
        auto_remove="force",
        command=(
            "python -m app.batch.runner "
            "--run-date {{ ds }} "
            "--output-dir /var/lib/confidential-drift"
        ),
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        mount_tmp_dir=False,
        mounts=[
            Mount(
                source="confidential_drift_data",
                target="/var/lib/confidential-drift",
                type="volume",
            ),
        ],
        environment={
            "APP_ENV": "batch",
        },
    )

    compute_drift
