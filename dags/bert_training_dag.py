import os
from datetime import datetime

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

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
    dataset_path = f"{dataset_mount_target}/{dataset_file_name}"

    artifacts_mount_type = os.environ.get("TRAIN_ARTIFACTS_MOUNT_TYPE", "volume")
    artifacts_mount_source = os.environ.get(
        "TRAIN_ARTIFACTS_MOUNT_SOURCE",
        "confidential_artifacts_data",
    )
    artifacts_mount_target = os.environ.get(
        "TRAIN_ARTIFACTS_MOUNT_TARGET", "/var/lib/confidential-artifacts"
    )

    train_model = DockerOperator(
        task_id="train_bert_classifier",
        image=app_image,
        api_version="auto",
        auto_remove="force",
        command=(
            "uv run --extra train python -m app.training.train_bert "
            f"--data-path {dataset_path} "
            f"--output-dir {artifacts_mount_target}/bert_classifier"
        ),
        docker_url=docker_url,
        network_mode=docker_network,
        mount_tmp_dir=False,
        mounts=[
            Mount(
                source=dataset_mount_source,
                target=dataset_mount_target,
                type=dataset_mount_type,
                read_only=True,
            ),
            Mount(
                source=artifacts_mount_source,
                target=artifacts_mount_target,
                type=artifacts_mount_type,
            ),
        ],
        environment={
            "APP_ENV": "training",
        },
    )

    train_model
