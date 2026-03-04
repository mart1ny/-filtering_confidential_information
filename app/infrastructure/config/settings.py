from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = Field(default="confidential-filter-service", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    risk_allow_threshold: float = Field(default=0.30, alias="RISK_ALLOW_THRESHOLD")
    risk_block_threshold: float = Field(default=0.70, alias="RISK_BLOCK_THRESHOLD")


settings = Settings()
