"""Authenticated ASGI entry point and initial MCP tools."""

from mcp.server import MCPServer
from mcp.server.auth.provider import TokenVerifier
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from trpg_mcp import __version__
from trpg_mcp.auth import create_auth
from trpg_mcp.config import Settings, settings
from trpg_mcp.consent import consent_response

SERVER_NAME = "MCP-TRPG"


def create_mcp_server(
    runtime_settings: Settings,
    *,
    token_verifier: TokenVerifier | None = None,
) -> MCPServer:
    """Build one MCP server with an injectable verifier for isolated tests."""
    auth_settings, default_verifier = create_auth(runtime_settings)
    server = MCPServer(
        SERVER_NAME,
        instructions=(
            "MCP-TRPG is an AI-guided tabletop role-playing game server. "
            "Every game request is authorized as the authenticated Supabase user."
        ),
        auth=auth_settings,
        token_verifier=token_verifier or default_verifier,
    )

    @server.tool(
        meta={"securitySchemes": [{"type": "oauth2", "scopes": []}]},
    )
    def get_server_info() -> dict[str, str]:
        """Return the server identity and transport used by this deployment."""
        return {
            "name": SERVER_NAME,
            "version": __version__,
            "transport": "streamable-http",
        }

    @server.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> Response:
        """Return a public liveness response without checking external dependencies."""
        return JSONResponse(
            {
                "status": "ok",
                "service": SERVER_NAME,
                "version": __version__,
            }
        )

    @server.custom_route("/oauth/consent", methods=["GET"])
    async def oauth_consent(request: Request) -> Response:
        """Render the public Supabase OAuth consent UI."""
        return consent_response(runtime_settings)

    return server


mcp = create_mcp_server(settings)
app = mcp.streamable_http_app()
