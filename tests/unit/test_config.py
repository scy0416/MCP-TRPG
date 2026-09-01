"""Tests for runtime configuration."""

import pytest

from trpg_mcp.config import Settings


def test_settings_use_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "HOST",
        "PORT",
        "SUPABASE_URL",
        "SUPABASE_AUTH_ISSUER",
        "SUPABASE_JWKS_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "MCP_RESOURCE_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    assert Settings.from_env() == Settings(host="127.0.0.1", port=8000)


@pytest.mark.parametrize("port", ["0", "65536", "not-a-number"])
def test_settings_reject_invalid_port(
    monkeypatch: pytest.MonkeyPatch,
    port: str,
) -> None:
    monkeypatch.setenv("PORT", port)

    with pytest.raises(ValueError, match="PORT must"):
        Settings.from_env()


def test_settings_derive_auth_urls_from_supabase_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co/")
    monkeypatch.setenv("MCP_RESOURCE_URL", "https://trpg.example.com/mcp")

    settings = Settings.from_env()

    assert settings.supabase_auth_issuer == "https://project.supabase.co/auth/v1"
    assert settings.supabase_jwks_url.endswith("/auth/v1/.well-known/jwks.json")
    assert settings.mcp_resource_url == "https://trpg.example.com/mcp"


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("SUPABASE_URL", "http://supabase.example.com", "HTTPS"),
        ("SUPABASE_AUTH_ISSUER", "not-a-url", "absolute HTTP URL"),
        ("MCP_RESOURCE_URL", "https://trpg.example.com/api", "/mcp endpoint"),
    ],
)
def test_settings_reject_unsafe_auth_urls(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
    message: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        Settings.from_env()
