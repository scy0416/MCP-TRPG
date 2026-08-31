"""Core MCP tools for campaign and character setup."""

from collections.abc import Mapping
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken

from trpg_mcp.game_repository import GameRepository

ABILITIES = ("str", "dex", "int", "cha")


def register_core_tools(server, repository: GameRepository) -> None:
    """Register the smallest persistent game loop before check mechanics."""

    @server.tool()
    async def create_campaign(title: str) -> dict[str, object]:
        """Create an active campaign owned by the authenticated user."""
        access_token = _require_access_token()
        _validate_text(title, "title", 120)
        return dict(await repository.create_campaign(access_token, title.strip()))

    @server.tool()
    async def create_character(
        campaign_id: str,
        name: str,
        stats: dict[str, int],
    ) -> dict[str, object]:
        """Create the authenticated user's one character with +0..+3 abilities."""
        access_token = _require_access_token()
        campaign_uuid = _validate_uuid(campaign_id, "campaign_id")
        _validate_text(name, "name", 80)
        validated_stats = _validate_stats(stats)
        return dict(
            await repository.create_character(
                access_token,
                campaign_uuid,
                name.strip(),
                validated_stats,
            )
        )

    @server.tool()
    async def get_game(campaign_id: str) -> dict[str, object]:
        """Read the authenticated user's AI-facing campaign context."""
        access_token = _require_access_token()
        game = await repository.get_game(access_token, _validate_uuid(campaign_id, "campaign_id"))
        if game is None:
            raise LookupError("campaign is not available to this user")
        return dict(game)


def _require_access_token() -> AccessToken:
    access_token = get_access_token()
    if access_token is None or not access_token.subject:
        raise PermissionError("authenticated MCP tool access is required")
    return access_token


def _validate_uuid(value: str, name: str) -> str:
    try:
        return str(UUID(value))
    except ValueError as error:
        raise ValueError(f"{name} must be a UUID") from error


def _validate_text(value: str, name: str, max_length: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
        raise ValueError(f"{name} must contain 1..{max_length} non-whitespace characters")


def _validate_stats(stats: Mapping[str, object]) -> dict[str, int]:
    if set(stats) != set(ABILITIES):
        raise ValueError("stats must contain exactly str, dex, int and cha")
    values = [stats[ability] for ability in ABILITIES]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValueError("ability modifiers must be integers")
    if sorted(values) != [0, 1, 2, 3]:
        raise ValueError("ability modifiers must be exactly 0, 1, 2 and 3")
    return {ability: int(stats[ability]) for ability in ABILITIES}
