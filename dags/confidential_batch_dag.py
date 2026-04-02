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
    docker_url = os.environ.get("DOCKER_URL", "unix://var/run/docker.sock")
    docker_network = os.environ.get("DOCKER_NETWORK_MODE", "bridge")

    drift_mount_type = os.environ.get("DRIFT_MOUNT_TYPE", "volume")
    drift_mount_source = os.environ.get("DRIFT_MOUNT_SOURCE", "confidential_drift_data")
    drift_mount_target = os.environ.get("DRIFT_MOUNT_TARGET", "/var/lib/confidential-drift")

    compute_drift = DockerOperator(
        task_id="compute_drift",
        image=app_image,
        api_version="auto",
        auto_remove="force",
        command=(
            "python -m app.batch.runner "
            "--run-date {{ ds }} "
            f"--output-dir {drift_mount_target}"
        ),
        docker_url=docker_url,
        network_mode=docker_network,
        mount_tmp_dir=False,
        mounts=[
            Mount(
                source=drift_mount_source,
                target=drift_mount_target,
                type=drift_mount_type,
            ),
        ],
        environment={
            "APP_ENV": "batch",
        },
    )

    compute_drift
