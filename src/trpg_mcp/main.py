"""Authenticated ASGI entry point and initial MCP tools."""

from mcp.server import MCPServer
from mcp.server.apps import Apps
from mcp.server.auth.provider import TokenVerifier
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from trpg_mcp import __version__
from trpg_mcp.auth import create_auth
from trpg_mcp.config import Settings, settings
from trpg_mcp.consent import consent_response
from trpg_mcp.dice_app import DICE_APP_HTML, DICE_RESOURCE_URI
from trpg_mcp.game_app import GAME_APP_HTML, GAME_RESOURCE_URI
from trpg_mcp.game_repository import GameRepository, SupabaseGameRepository
from trpg_mcp.instructions import SERVER_INSTRUCTIONS
from trpg_mcp.resources import ResourceProvider, register_resources
from trpg_mcp.tools import register_core_tools

SERVER_NAME = "MCP-TRPG"


def create_mcp_server(
    runtime_settings: Settings,
    *,
    token_verifier: TokenVerifier | None = None,
    resource_provider: ResourceProvider | None = None,
    game_repository: GameRepository | None = None,
) -> MCPServer:
    """Build one MCP server with an injectable verifier for isolated tests."""
    auth_settings, default_verifier = create_auth(runtime_settings)
    apps = Apps()
    apps.add_html_resource(
        DICE_RESOURCE_URI,
        DICE_APP_HTML,
        name="trpg_dice_app",
        title="MCP-TRPG Dice",
        description="Roll a pending ability check and submit raw dice results",
        prefers_border=True,
    )
    apps.add_html_resource(
        GAME_RESOURCE_URI,
        GAME_APP_HTML,
        name="trpg_game_app",
        title="MCP-TRPG Game",
        description="Display the authenticated campaign game snapshot",
        prefers_border=True,
    )
    server = MCPServer(
        SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        auth=auth_settings,
        token_verifier=token_verifier or default_verifier,
        extensions=[apps],
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

    repository = game_repository or SupabaseGameRepository(runtime_settings)
    register_resources(server, resource_provider or repository)
    register_core_tools(
        server,
        repository,
        dice_resource_uri=DICE_RESOURCE_URI,
        game_resource_uri=GAME_RESOURCE_URI,
    )
    return server


mcp = create_mcp_server(settings)
app = mcp.streamable_http_app(host=settings.host)
