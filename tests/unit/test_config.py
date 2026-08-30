"""Tests for runtime configuration."""

import pytest

from trpg_mcp.config import Settings


def test_settings_use_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    assert Settings.from_env() == Settings(host="127.0.0.1", port=8000)


@pytest.mark.parametrize("port", ["0", "65536", "not-a-number"])
def test_settings_reject_invalid_port(
    monkeypatch: pytest.MonkeyPatch,
    port: str,
) -> None:
    monkeypatch.setenv("PORT", port)

    with pytest.raises(ValueError, match="PORT must"):
        Settings.from_env()
