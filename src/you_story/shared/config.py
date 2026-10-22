"""Runtime configuration deliberately has no migration credential setting."""

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="YOU_STORY_", extra="ignore", hide_input_in_errors=True
    )
    database_url: SecretStr

    @field_validator("database_url")
    @classmethod
    def runtime_database_only(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError:
            raise ValueError("A valid runtime PostgreSQL URL is required") from None
        if url.drivername != "postgresql+psycopg" or url.username != "app_runtime":
            raise ValueError("Only the app_runtime PostgreSQL identity is permitted")
        return value
