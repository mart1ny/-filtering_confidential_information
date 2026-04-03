import os
from datetime import datetime

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount


def _normalize_mount_type(source: str, configured_type: str) -> str:
    if source.startswith("/"):
        return "bind"
    return configured_type


with DAG(
    dag_id="bert_training_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="@weekly",
    catchup=False,
    max_active_runs=1,
    tags=["ml", "training", "bert"],
) as dag:
    app_image = os.environ.get("APP_IMAGE", "confidential-filter-service:local")
    docker_url = os.environ.get("DOCKER_URL", "unix://var/run/docker.sock")
    docker_network = os.environ.get("DOCKER_NETWORK_MODE", "bridge")

    dataset_mount_type = os.environ.get("TRAIN_DATASET_MOUNT_TYPE", "volume")
    dataset_mount_source = os.environ.get("TRAIN_DATASET_MOUNT_SOURCE", "confidential_dataset_data")
    dataset_mount_target = os.environ.get(
        "TRAIN_DATASET_MOUNT_TARGET", "/var/lib/confidential-dataset"
    )
    dataset_file_name = os.environ.get("TRAIN_DATASET_FILE", "ds.parquet")
    dataset_uri = os.environ.get("TRAIN_DATASET_URI")
    dataset_path = dataset_uri or f"{dataset_mount_target}/{dataset_file_name}"
    review_mount_type = os.environ.get("REVIEW_MOUNT_TYPE", "volume")
    review_mount_source = os.environ.get("REVIEW_MOUNT_SOURCE", "confidential_review_data")
    review_mount_target = os.environ.get("REVIEW_MOUNT_TARGET", "/var/lib/confidential-review")

    artifacts_mount_type = os.environ.get("TRAIN_ARTIFACTS_MOUNT_TYPE", "volume")
    artifacts_mount_source = os.environ.get(
        "TRAIN_ARTIFACTS_MOUNT_SOURCE",
        "confidential_artifacts_data",
    )
    artifacts_mount_target = os.environ.get(
        "TRAIN_ARTIFACTS_MOUNT_TARGET", "/var/lib/confidential-artifacts"
    )
    dataset_mount_type = _normalize_mount_type(dataset_mount_source, dataset_mount_type)
    review_mount_type = _normalize_mount_type(review_mount_source, review_mount_type)
    artifacts_mount_type = _normalize_mount_type(artifacts_mount_source, artifacts_mount_type)
    mounts = [
        Mount(
            source=artifacts_mount_source,
            target=artifacts_mount_target,
            type=artifacts_mount_type,
        ),
        Mount(
            source=review_mount_source,
            target=review_mount_target,
            type=review_mount_type,
        ),
    ]
    if not dataset_path.startswith("s3://"):
        mounts.insert(
            0,
            Mount(
                source=dataset_mount_source,
                target=dataset_mount_target,
                type=dataset_mount_type,
                read_only=True,
            ),
        )
    training_env = {"APP_ENV": "training"}
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "S3_ENDPOINT_URL",
        "TRAIN_RESULTS_S3_URI_PREFIX",
        "REVIEW_STORAGE_DIR",
        "REVIEW_DATABASE_URL",
        "REVIEW_DB_HOST",
        "REVIEW_DB_PORT",
        "REVIEW_DB_NAME",
        "REVIEW_DB_USER",
        "REVIEW_DB_PASSWORD",
    ):
        value = os.environ.get(key)
        if value:
            training_env[key] = value
    training_env.setdefault("REVIEW_STORAGE_DIR", review_mount_target)

    export_review_dataset = DockerOperator(
        task_id="export_review_dataset",
        image=app_image,
        user="0:0",
        api_version="auto",
        auto_remove="force",
        command=(
            "python -m app.review.export_dataset "
            f"--output-path {dataset_mount_target}/{dataset_file_name}"
        ),
        docker_url=docker_url,
        network_mode=docker_network,
        mount_tmp_dir=False,
        mounts=mounts,
        environment=training_env,
    )

    train_model = DockerOperator(
        task_id="train_bert_classifier",
        image=app_image,
        user="0:0",
        api_version="auto",
        auto_remove="force",
        command=(
            "python -m app.training.train_bert "
            f"--data-path {dataset_path} "
            f"--output-dir {artifacts_mount_target}/bert_classifier"
        ),
        docker_url=docker_url,
        network_mode=docker_network,
        mount_tmp_dir=False,
        mounts=mounts,
        environment=training_env,
    )

    if dataset_uri and dataset_uri.startswith("s3://"):
        train_model
    else:
        export_review_dataset >> train_model
