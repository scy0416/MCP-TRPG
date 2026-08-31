"""MCP and ASGI integration tests for the initial server."""

import time
from collections.abc import Iterator

import pytest
from mcp import Client
from mcp.server.auth.provider import AccessToken
from starlette.testclient import TestClient

from trpg_mcp.config import Settings
from trpg_mcp.main import create_mcp_server, mcp


class StaticTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        if token != "valid-test-token":
            return None
        return AccessToken(
            token=token,
            client_id="test-client",
            scopes=[],
            expires_at=int(time.time()) + 300,
            resource="http://127.0.0.1:8000/mcp",
            subject="10000000-0000-0000-0000-000000000001",
            claims={"iss": "http://127.0.0.1:54321/auth/v1"},
        )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def http_client() -> Iterator[TestClient]:
    server = create_mcp_server(Settings())
    with TestClient(
        server.streamable_http_app(),
        base_url="http://127.0.0.1:8000",
    ) as client:
        yield client


@pytest.mark.anyio
async def test_server_lists_and_calls_info_tool() -> None:
    async with Client(mcp, raise_exceptions=True) as client:
        tools = await client.list_tools()
        assert [tool.name for tool in tools.tools] == ["get_server_info"]
        assert tools.tools[0].meta == {"securitySchemes": [{"type": "oauth2", "scopes": []}]}

        result = await client.call_tool("get_server_info", {})

    assert result.is_error is False
    assert result.structured_content == {
        "name": "MCP-TRPG",
        "version": "0.1.0",
        "transport": "streamable-http",
    }


def test_health_endpoint(http_client: TestClient) -> None:
    response = http_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "MCP-TRPG",
        "version": "0.1.0",
    }


def test_mcp_endpoint_requires_bearer_token(http_client: TestClient) -> None:
    response = http_client.post("/mcp")

    assert response.status_code == 401
    assert "invalid_token" in response.headers["www-authenticate"]
    assert (
        'resource_metadata="http://127.0.0.1:8000/.well-known/oauth-protected-resource/mcp"'
        in response.headers["www-authenticate"]
    )


def test_protected_resource_metadata_is_public(http_client: TestClient) -> None:
    response = http_client.get("/.well-known/oauth-protected-resource/mcp")

    assert response.status_code == 200
    assert response.json() == {
        "resource": "http://127.0.0.1:8000/mcp",
        "authorization_servers": ["http://127.0.0.1:54321/auth/v1"],
        "scopes_supported": [],
        "bearer_methods_supported": ["header"],
    }


def test_valid_bearer_token_reaches_mcp_transport() -> None:
    server = create_mcp_server(Settings(), token_verifier=StaticTokenVerifier())
    authenticated_app = server.streamable_http_app(json_response=True, stateless_http=True)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }

    with TestClient(authenticated_app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/mcp",
            json=request,
            headers={
                "Authorization": "Bearer valid-test-token",
                "Accept": "application/json, text/event-stream",
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["name"] == "MCP-TRPG"


def test_consent_page_fails_closed_without_publishable_key(http_client: TestClient) -> None:
    response = http_client.get("/oauth/consent?authorization_id=test")

    assert response.status_code == 503
    assert "SUPABASE_PUBLISHABLE_KEY" in response.text


def test_consent_page_uses_public_configuration_safely() -> None:
    runtime_settings = Settings(supabase_publishable_key="test-publishable-key")
    server = create_mcp_server(runtime_settings, token_verifier=StaticTokenVerifier())

    with TestClient(
        server.streamable_http_app(),
        base_url="http://127.0.0.1:8000",
    ) as client:
        response = client.get("/oauth/consent?authorization_id=test")

    assert response.status_code == 200
    assert "MCP-TRPG 연결 승인" in response.text
    assert "test-publishable-key" not in response.text
    assert "Content-Security-Policy" in response.headers
    assert response.headers["cache-control"] == "no-store"
