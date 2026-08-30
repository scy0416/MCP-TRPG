"""Verify the deployed MCP endpoint through the real Streamable HTTP transport."""

import asyncio
from os import environ

from mcp import Client


async def main() -> None:
    server_url = environ.get("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")

    async with Client(server_url) as client:
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools.tools]
        if tool_names != ["get_server_info"]:
            raise RuntimeError(f"Unexpected tool list: {tool_names}")

        result = await client.call_tool("get_server_info", {})
        if result.is_error:
            raise RuntimeError(f"get_server_info failed: {result.content}")

    print(f"Streamable HTTP smoke test passed: {server_url}")


if __name__ == "__main__":
    asyncio.run(main())
