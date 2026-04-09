import os
from datetime import datetime

from airflow import DAG
from airflow.exceptions import AirflowNotFoundException
from airflow.hooks.base import BaseHook
from airflow.models.param import Param
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

from airflow_runtime_connections import build_runtime_env


def _normalize_mount_type(source: str, configured_type: str) -> str:
    if source.startswith("/"):
        return "bind"
    return configured_type


with DAG(
    dag_id="confidential_metrics_batch",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    params={
        "use_today": Param(
            True,
            type="boolean",
            title="Use today's date",
            description="If enabled, the DAG uses ds and ignores the manual date field.",
        ),
        "end_date": Param(
            None,
            type=["null", "string"],
            format="date",
            title="Manual date",
            description=(
                "Historical date in YYYY-MM-DD format used when " "the toggle is disabled."
            ),
        ),
    },
    tags=["ml", "drift", "idempotent"],
) as dag:
    app_image = os.environ.get("APP_IMAGE", "confidential-filter-service:local")
    docker_url = os.environ.get("DOCKER_URL", "unix://var/run/docker.sock")
    docker_network = os.environ.get("DOCKER_NETWORK_MODE", "bridge")

    drift_mount_type = os.environ.get("DRIFT_MOUNT_TYPE", "volume")
    drift_mount_source = os.environ.get("DRIFT_MOUNT_SOURCE", "confidential_drift_data")
    drift_mount_target = os.environ.get("DRIFT_MOUNT_TARGET", "/var/lib/confidential-drift")
    drift_mount_type = _normalize_mount_type(drift_mount_source, drift_mount_type)
    try:
        review_db_connection = BaseHook.get_connection("review_db")
    except AirflowNotFoundException:
        review_db_connection = None

    try:
        s3_connection = BaseHook.get_connection("regru_s3")
    except AirflowNotFoundException:
        s3_connection = None

    runtime_env = build_runtime_env(
        "batch",
        ("DRIFT_RESULTS_S3_URI_PREFIX",),
        review_db_connection=review_db_connection,
        s3_connection=s3_connection,
    )
    run_date_template = "{{ ds if params.use_today else (params.end_date or ds) }}"
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
            f"--run-date {run_date_template} "
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
            f"--run-date {run_date_template} "
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
            f"--run-date {run_date_template} "
            f"--output-dir {drift_mount_target}"
        ),
        docker_url=docker_url,
        network_mode=docker_network,
        mount_tmp_dir=False,
        mounts=shared_mounts,
        environment=runtime_env,
    )

    prepare_drift_output >> compute_drift >> publish_drift
