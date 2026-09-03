"""Validated environment configuration for the complete service."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Load deployment choices from INCIDENT_AGENT_-prefixed variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="INCIDENT_AGENT_",
        extra="ignore",
        populate_by_name=True,
    )

    api_token: SecretStr = SecretStr("local-demo-token")
    model_provider: Literal["demo", "openai"] = "demo"
    openai_model: str = "gpt-5.6-luna"
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )
    checkpoint_path: Path = Path(".data/incident-agent.sqlite")
    runbook_dir: Path = Path("knowledge/runbooks")
    mcp_command: str | None = None
    mcp_args_json: str = "[]"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)

    @field_validator("mcp_command", mode="before")
    @classmethod
    def blank_mcp_command_means_disabled(cls, value: object) -> object:
        """Treat an empty .env value as no external MCP process."""

        return None if value == "" else value

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def blank_openai_key_means_missing(cls, value: object) -> object:
        """Keep an empty copied template from looking like a usable API key."""

        return None if value == "" else value

    @property
    def api_token_value(self) -> str:
        """Reveal the HTTP secret only at the authentication boundary."""

        return self.api_token.get_secret_value()

    def mcp_args(self) -> tuple[str, ...]:
        """Validate the JSON environment value as a list of process arguments."""

        value = json.loads(self.mcp_args_json)
        if not isinstance(value, list) or not all(
            isinstance(argument, str) for argument in value
        ):
            raise ValueError("INCIDENT_AGENT_MCP_ARGS_JSON must be a JSON string list")
        return tuple(value)


@lru_cache(maxsize=1)
def load_settings() -> AppSettings:
    """Create and cache the process-wide validated settings object."""

    return AppSettings()
