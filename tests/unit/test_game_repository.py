"""Unit tests for the Supabase persistence boundary."""

import pytest
from mcp.server.auth.provider import AccessToken

from trpg_mcp.game_repository import SupabaseRestClient, SupabaseRestError, _safe_error_detail


@pytest.fixture
def access_token() -> AccessToken:
    return AccessToken(token="test-token", client_id="test-client", scopes=[], subject="user")


@pytest.mark.anyio
async def test_rest_client_fails_closed_without_publishable_key(access_token: AccessToken) -> None:
    client = SupabaseRestClient("https://project.supabase.co", "")

    with pytest.raises(SupabaseRestError, match="not configured") as error:
        await client.request(table="campaigns", method="GET", access_token=access_token)

    assert error.value.status_code == 503


def test_upstream_error_detail_is_bounded_and_safe() -> None:
    assert _safe_error_detail(b'{"message":"duplicate title"}') == "duplicate title"
    assert _safe_error_detail(b'{"message":"x"' + b"a" * 500) == "upstream request rejected"
