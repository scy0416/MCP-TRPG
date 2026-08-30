"""MCP and ASGI integration tests for the initial server."""

import pytest
from mcp import Client
from starlette.testclient import TestClient

from trpg_mcp.main import app, mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_server_lists_and_calls_info_tool() -> None:
    async with Client(mcp, raise_exceptions=True) as client:
        tools = await client.list_tools()
        assert [tool.name for tool in tools.tools] == ["get_server_info"]

        result = await client.call_tool("get_server_info", {})

    assert result.is_error is False
    assert result.structured_content == {
        "name": "MCP-TRPG",
        "version": "0.1.0",
        "transport": "streamable-http",
    }


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "MCP-TRPG",
        "version": "0.1.0",
    }
