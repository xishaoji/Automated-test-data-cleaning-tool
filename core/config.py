"""Centralized, typed configuration loaded from environment variables.

We use ``pydantic-settings`` so that:
- All env-driven knobs live in one place with validation and defaults.
- Tests can inject a custom ``Settings`` instance instead of monkey-patching os.environ.
- The rest of the codebase depends on ``Settings`` fields, not on ``os.getenv`` calls.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the test-log copilot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM ---
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL"
    )
    llm_model_name: str = Field(default="deepseek-chat", validation_alias="LLM_MODEL_NAME")
    llm_temperature: float = Field(default=0.0, validation_alias="LLM_TEMPERATURE")

    # --- Sandbox ---
    sandbox_image: str = Field(default="pandas-sandbox:latest", validation_alias="SANDBOX_IMAGE")
    sandbox_memory: str = Field(default="256m", validation_alias="SANDBOX_MEMORY")
    sandbox_cpu_quota: int = Field(default=50_000, validation_alias="SANDBOX_CPU_QUOTA")
    sandbox_cpu_period: int = Field(default=100_000, validation_alias="SANDBOX_CPU_PERIOD")
    sandbox_pids_limit: int = Field(default=64, validation_alias="SANDBOX_PIDS_LIMIT")
    sandbox_timeout_seconds: int = Field(default=30, validation_alias="SANDBOX_TIMEOUT_SECONDS")

    # --- Logging ---
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_json: bool = Field(default=False, validation_alias="LOG_JSON")

    # --- Safety knobs ---
    max_upload_mb: int = Field(default=50, validation_alias="MAX_UPLOAD_MB")
    max_error_retries: int = Field(default=3, validation_alias="MAX_ERROR_RETRIES")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide singleton ``Settings`` instance.

    Wrapped in ``lru_cache`` so repeated imports don't re-read the .env file.
    Tests can call ``get_settings.cache_clear()`` when they need a fresh instance.
    """

    return Settings()
