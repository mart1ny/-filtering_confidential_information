from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="confidential-filter-service", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    risk_allow_threshold: float = Field(default=0.30, alias="RISK_ALLOW_THRESHOLD")
    risk_block_threshold: float = Field(default=0.70, alias="RISK_BLOCK_THRESHOLD")
    detector_backend: str = Field(default="rules", alias="DETECTOR_BACKEND")
    model_path: str = Field(default="bert_classifier/model", alias="MODEL_PATH")
    model_name: str = Field(default="distilbert-base-uncased", alias="MODEL_NAME")
    model_device: int = Field(default=-1, alias="MODEL_DEVICE")
    review_storage_dir: str = Field(default="review_data", alias="REVIEW_STORAGE_DIR")
    review_database_url: str | None = Field(default=None, alias="REVIEW_DATABASE_URL")
    review_db_host: str | None = Field(default=None, alias="REVIEW_DB_HOST")
    review_db_port: int = Field(default=5432, alias="REVIEW_DB_PORT")
    review_db_name: str | None = Field(default=None, alias="REVIEW_DB_NAME")
    review_db_user: str | None = Field(default=None, alias="REVIEW_DB_USER")
    review_db_password: str | None = Field(default=None, alias="REVIEW_DB_PASSWORD")

    @property
    def resolved_review_database_url(self) -> str | None:
        if self.review_database_url:
            return self.review_database_url
        required_parts = (
            self.review_db_host,
            self.review_db_name,
            self.review_db_user,
            self.review_db_password,
        )
        if not all(required_parts):
            return None
        return (
            "postgresql://"
            f"{quote_plus(self.review_db_user)}:{quote_plus(self.review_db_password)}"
            f"@{self.review_db_host}:{self.review_db_port}/{self.review_db_name}"
        )


settings = Settings()
