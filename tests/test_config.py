"""Tests for core.config — validates env-driven settings loading."""

from __future__ import annotations

import pytest

from core.config import Settings, get_settings


class TestSettings:
    """Verify that Settings picks up env vars and applies defaults."""

    def test_defaults(self):
        """Without any env vars, defaults should be sensible."""
        s = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.llm_model_name == "deepseek-chat"
        assert s.llm_temperature == 0.0
        assert s.sandbox_memory == "256m"
        assert s.max_error_retries == 3

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch):
        """Env vars should override defaults."""
        monkeypatch.setenv("LLM_MODEL_NAME", "gpt-4o")
        monkeypatch.setenv("SANDBOX_TIMEOUT_SECONDS", "60")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.llm_model_name == "gpt-4o"
        assert s.sandbox_timeout_seconds == 60

    def test_get_settings_caches(self):
        """get_settings should return the same instance on repeated calls."""
        get_settings.cache_clear()
        a = get_settings()
        b = get_settings()
        assert a is b
        get_settings.cache_clear()
