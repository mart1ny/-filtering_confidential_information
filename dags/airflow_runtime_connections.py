from __future__ import annotations

import os
from typing import Any

from airflow.models.connection import Connection


def build_runtime_env(
    app_env: str,
    extra_env_keys: tuple[str, ...],
    review_db_connection: Connection | None = None,
    s3_connection: Connection | None = None,
) -> dict[str, str]:
    runtime_env = {"APP_ENV": app_env}
    runtime_env.update(_build_review_db_env(review_db_connection))
    runtime_env.update(_build_s3_env(s3_connection))
    runtime_env.update(_read_env_values(extra_env_keys))
    return runtime_env


def _build_review_db_env(connection: Connection | None) -> dict[str, str]:
    if connection is None:
        return _read_env_values(
            (
                "REVIEW_DATABASE_URL",
                "REVIEW_DB_HOST",
                "REVIEW_DB_PORT",
                "REVIEW_DB_NAME",
                "REVIEW_DB_USER",
                "REVIEW_DB_PASSWORD",
            )
        )

    runtime_env: dict[str, str] = {}
    if connection.host:
        runtime_env["REVIEW_DB_HOST"] = connection.host
    if connection.port is not None:
        runtime_env["REVIEW_DB_PORT"] = str(connection.port)
    if connection.schema:
        runtime_env["REVIEW_DB_NAME"] = connection.schema
    if connection.login:
        runtime_env["REVIEW_DB_USER"] = connection.login
    if connection.password:
        runtime_env["REVIEW_DB_PASSWORD"] = connection.password
    return runtime_env


def _build_s3_env(connection: Connection | None) -> dict[str, str]:
    if connection is None:
        return _read_env_values(
            (
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN",
                "AWS_REGION",
                "AWS_DEFAULT_REGION",
                "S3_ENDPOINT_URL",
            )
        )

    runtime_env: dict[str, str] = {}
    if connection.login:
        runtime_env["AWS_ACCESS_KEY_ID"] = connection.login
    if connection.password:
        runtime_env["AWS_SECRET_ACCESS_KEY"] = connection.password

    connection_extra = connection.extra_dejson
    session_token = _first_present(connection_extra, "aws_session_token", "session_token")
    if session_token:
        runtime_env["AWS_SESSION_TOKEN"] = session_token

    region = _first_present(
        connection_extra,
        "region_name",
        "region",
        "aws_region",
        "aws_default_region",
    )
    if region:
        runtime_env["AWS_REGION"] = region
        runtime_env["AWS_DEFAULT_REGION"] = region

    endpoint_url = _first_present(connection_extra, "endpoint_url", "s3_endpoint_url")
    if endpoint_url:
        runtime_env["S3_ENDPOINT_URL"] = endpoint_url
    return runtime_env


def _read_env_values(keys: tuple[str, ...]) -> dict[str, str]:
    return {key: value for key in keys if (value := os.environ.get(key))}


def _first_present(connection_extra: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = connection_extra.get(key)
        if value:
            return str(value)
    return None
