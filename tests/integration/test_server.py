"""MCP and ASGI integration tests for the initial server."""

import time
from collections.abc import Iterator, Mapping

import pytest
from mcp import Client
from mcp.server.auth.provider import AccessToken
from starlette.testclient import TestClient

from trpg_mcp.config import Settings
from trpg_mcp.main import create_mcp_server, mcp
from trpg_mcp.resources import SnapshotResourceProvider


class FakeGameRepository(SnapshotResourceProvider):
    async def create_campaign(self, access_token: AccessToken, title: str) -> Mapping[str, object]:
        return {"id": "10000000-0000-0000-0000-000000000003", "title": title, "status": "active"}

    async def create_character(
        self,
        access_token: AccessToken,
        campaign_id: str,
        name: str,
        stats: Mapping[str, int],
    ) -> Mapping[str, object]:
        return {"id": "10000000-0000-0000-0000-000000000004", "name": name, "stats": dict(stats)}

    async def get_game(
        self, access_token: AccessToken, campaign_id: str
    ) -> Mapping[str, object] | None:
        return {"campaign": {"id": campaign_id, "title": "Tower", "status": "active"}}

    async def create_check(
        self,
        access_token: AccessToken,
        campaign_id: str,
        character_id: str,
        check_type: str,
        dice_spec: Mapping[str, int],
        difficulty: int,
        context: str,
    ) -> Mapping[str, object]:
        return {
            "check_id": "10000000-0000-0000-0000-000000000005",
            "label": f"{check_type.upper()} Check",
            "dice": dict(dice_spec),
            "modifier": 3,
            "difficulty": difficulty,
            "reason": context,
            "status": "pending",
        }


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
        assert [tool.name for tool in tools.tools] == [
            "get_server_info",
            "create_campaign",
            "create_character",
            "get_game",
            "create_check",
        ]
        assert tools.tools[0].meta == {"securitySchemes": [{"type": "oauth2", "scopes": []}]}

        result = await client.call_tool("get_server_info", {})
        assert result.is_error is False
        assert result.structured_content == {
            "name": "MCP-TRPG",
            "version": "0.1.0",
            "transport": "streamable-http",
        }

        resources = await client.list_resources()
        assert [resource.uri for resource in resources.resources] == ["trpg://rules/core"]
        templates = await client.list_resource_templates()
        assert {template.uri_template for template in templates.resource_templates} == {
            "trpg://campaign/{campaign_id}/context",
            "trpg://campaign/{campaign_id}/scene",
            "trpg://campaign/{campaign_id}/history/recent",
        }
        rules = await client.read_resource("trpg://rules/core")
        assert "AI GM" in rules.contents[0].text


def test_campaign_resource_context_is_scoped_and_sanitized() -> None:
    provider = SnapshotResourceProvider()
    campaign_id = "10000000-0000-0000-0000-000000000002"
    provider.put(
        campaign_id,
        "10000000-0000-0000-0000-000000000001",
        {
            "context": {
                "campaign": {"id": campaign_id, "title": "Tower", "owner_id": "secret"},
                "character": {"name": "Arin", "user_id": "secret", "hp": 13},
            }
        },
    )
    server = create_mcp_server(
        Settings(),
        token_verifier=StaticTokenVerifier(),
        resource_provider=provider,
        game_repository=FakeGameRepository(),
    )
    app = server.streamable_http_app(json_response=True, stateless_http=True)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "resources/read",
        "params": {"uri": f"trpg://campaign/{campaign_id}/context"},
    }

    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/mcp",
            json=request,
            headers={
                "Authorization": "Bearer valid-test-token",
                "Accept": "application/json, text/event-stream",
            },
        )

    assert response.status_code == 200
    body = response.json()["result"]["contents"][0]["text"]
    assert "Tower" in body
    assert "owner_id" not in body
    assert "user_id" not in body


def test_core_tool_uses_authenticated_repository() -> None:
    server = create_mcp_server(
        Settings(), token_verifier=StaticTokenVerifier(), game_repository=FakeGameRepository()
    )
    app = server.streamable_http_app(json_response=True, stateless_http=True)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "create_character",
            "arguments": {
                "campaign_id": "10000000-0000-0000-0000-000000000002",
                "name": "Arin",
                "stats": {"str": 3, "dex": 2, "int": 1, "cha": 0},
            },
        },
    }

    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/mcp",
            json=request,
            headers={
                "Authorization": "Bearer valid-test-token",
                "Accept": "application/json, text/event-stream",
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["structuredContent"]["name"] == "Arin"


def test_create_check_does_not_accept_a_client_modifier() -> None:
    server = create_mcp_server(
        Settings(), token_verifier=StaticTokenVerifier(), game_repository=FakeGameRepository()
    )
    app = server.streamable_http_app(json_response=True, stateless_http=True)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "create_check",
            "arguments": {
                "campaign_id": "10000000-0000-0000-0000-000000000002",
                "character_id": "10000000-0000-0000-0000-000000000004",
                "ability": "strength",
                "dice_spec": {"count": 1, "sides": 20},
                "difficulty": 15,
                "reason": "문을 부순다",
            },
        },
    }

    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/mcp",
            json=request,
            headers={
                "Authorization": "Bearer valid-test-token",
                "Accept": "application/json, text/event-stream",
            },
        )

    assert response.status_code == 200
    result = response.json()["result"]["structuredContent"]
    assert result["modifier"] == 3
    assert result["status"] == "pending"


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
