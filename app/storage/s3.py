from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse


def upload_file_if_configured(file_path: Path, s3_uri_prefix: str | None) -> None:
    if not s3_uri_prefix:
        return

    bucket, prefix = _parse_s3_uri(s3_uri_prefix)
    key = _join_s3_key(prefix, file_path.name)
    _create_s3_client().upload_file(str(file_path), bucket, key)


def upload_directory_if_configured(directory: Path, s3_uri_prefix: str | None) -> None:
    if not s3_uri_prefix:
        return

    bucket, prefix = _parse_s3_uri(s3_uri_prefix)
    for file_path in _iter_files(directory):
        relative_key = file_path.relative_to(directory).as_posix()
        key = _join_s3_key(prefix, relative_key)
        _create_s3_client().upload_file(str(file_path), bucket, key)


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    normalized_uri = uri
    if uri.startswith("s3:/") and not uri.startswith("s3://"):
        normalized_uri = uri.replace("s3:/", "s3://", 1)
    parsed = urlparse(normalized_uri)
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    if not bucket:
        raise ValueError(f"Invalid S3 URI: {uri}")
    return bucket, prefix


def _join_s3_key(prefix: str, suffix: str) -> str:
    return f"{prefix.rstrip('/')}/{suffix.lstrip('/')}" if prefix else suffix.lstrip("/")


def _iter_files(directory: Path) -> Iterator[Path]:
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            yield path


def _create_s3_client():
    try:
        import boto3
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "boto3 is required to upload results to S3. "
            "Install training dependencies (`uv sync --extra train`)."
        ) from exc

    endpoint_url = os.environ.get("S3_ENDPOINT_URL")
    region_name = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    client_kwargs = {}
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
    if region_name:
        client_kwargs["region_name"] = region_name
    return boto3.client("s3", **client_kwargs)
