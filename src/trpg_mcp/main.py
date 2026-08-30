"""ASGI entry point and initial MCP tools."""

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from trpg_mcp import __version__

SERVER_NAME = "MCP-TRPG"

mcp = MCPServer(
    SERVER_NAME,
    instructions=(
        "MCP-TRPG is an AI-guided tabletop role-playing game server. "
        "Game tools will be introduced incrementally after the local transport is verified."
    ),
)


@mcp.tool()
def get_server_info() -> dict[str, str]:
    """Return the server identity and transport used by this deployment."""
    return {
        "name": SERVER_NAME,
        "version": __version__,
        "transport": "streamable-http",
    }


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> Response:
    """Return a public liveness response without checking external dependencies."""
    return JSONResponse(
        {
            "status": "ok",
            "service": SERVER_NAME,
            "version": __version__,
        }
    )


app = mcp.streamable_http_app()
