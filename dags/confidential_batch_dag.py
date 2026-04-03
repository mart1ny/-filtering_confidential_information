import os
from datetime import datetime

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount


def _normalize_mount_type(source: str, configured_type: str) -> str:
    if source.startswith("/"):
        return "bind"
    return configured_type


def _build_runtime_env(app_env: str, extra_keys: tuple[str, ...]) -> dict[str, str]:
    runtime_env = {"APP_ENV": app_env}
    for key in extra_keys:
        value = os.environ.get(key)
        if value:
            runtime_env[key] = value
    return runtime_env


with DAG(
    dag_id="confidential_metrics_batch",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["ml", "drift", "idempotent"],
) as dag:
    app_image = os.environ.get("APP_IMAGE", "confidential-filter-service:local")
    docker_url = os.environ.get("DOCKER_URL", "unix://var/run/docker.sock")
    docker_network = os.environ.get("DOCKER_NETWORK_MODE", "bridge")

    drift_mount_type = os.environ.get("DRIFT_MOUNT_TYPE", "volume")
    drift_mount_source = os.environ.get("DRIFT_MOUNT_SOURCE", "confidential_drift_data")
    drift_mount_target = os.environ.get("DRIFT_MOUNT_TARGET", "/var/lib/confidential-drift")
    drift_mount_type = _normalize_mount_type(drift_mount_source, drift_mount_type)
    runtime_env = _build_runtime_env(
        "batch",
        (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_REGION",
            "AWS_DEFAULT_REGION",
            "S3_ENDPOINT_URL",
            "DRIFT_RESULTS_S3_URI_PREFIX",
            "REVIEW_DATABASE_URL",
            "REVIEW_DB_HOST",
            "REVIEW_DB_PORT",
            "REVIEW_DB_NAME",
            "REVIEW_DB_USER",
            "REVIEW_DB_PASSWORD",
        ),
    )
    shared_mounts = [
        Mount(
            source=drift_mount_source,
            target=drift_mount_target,
            type=drift_mount_type,
        ),
    ]

    prepare_drift_output = DockerOperator(
        task_id="prepare_drift_output",
        image=app_image,
        user="0:0",
        api_version="auto",
        auto_remove="force",
        command=(
            "python -m app.batch.runner "
            "--action prepare "
            "--run-date {{ ds }} "
            f"--output-dir {drift_mount_target}"
        ),
        docker_url=docker_url,
        network_mode=docker_network,
        mount_tmp_dir=False,
        mounts=shared_mounts,
        environment=runtime_env,
    )

    compute_drift = DockerOperator(
        task_id="compute_drift",
        image=app_image,
        user="0:0",
        api_version="auto",
        auto_remove="force",
        command=(
            "python -m app.batch.runner "
            "--action compute "
            "--run-date {{ ds }} "
            f"--output-dir {drift_mount_target}"
        ),
        docker_url=docker_url,
        network_mode=docker_network,
        mount_tmp_dir=False,
        mounts=shared_mounts,
        environment=runtime_env,
    )

    publish_drift = DockerOperator(
        task_id="publish_drift",
        image=app_image,
        user="0:0",
        api_version="auto",
        auto_remove="force",
        command=(
            "python -m app.batch.runner "
            "--action publish "
            "--run-date {{ ds }} "
            f"--output-dir {drift_mount_target}"
        ),
        docker_url=docker_url,
        network_mode=docker_network,
        mount_tmp_dir=False,
        mounts=shared_mounts,
        environment=runtime_env,
    )

    prepare_drift_output >> compute_drift >> publish_drift
