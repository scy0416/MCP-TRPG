"""Tests for the Supabase setup validator."""

import pytest

from scripts.check_supabase_setup import validate_local_config, validate_remote_environment


def test_local_supabase_config_is_valid() -> None:
    validate_local_config()


def test_remote_environment_requires_all_public_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_PROJECT_REF"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="SUPABASE_URL"):
        validate_remote_environment()


def test_remote_environment_requires_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    monkeypatch.setenv("SUPABASE_PROJECT_REF", "test-project-ref")
    monkeypatch.setenv("MCP_RESOURCE_URL", "https://trpg.example.com/mcp")

    with pytest.raises(ValueError, match="HTTPS"):
        validate_remote_environment()
