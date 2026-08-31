"""Core MCP tools for campaign and character setup."""

from collections.abc import Mapping
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken

from trpg_mcp.game_repository import GameRepository

ABILITIES = ("str", "dex", "int", "cha")
ABILITY_ALIASES = {
    "str": "str",
    "strength": "str",
    "dex": "dex",
    "dexterity": "dex",
    "int": "int",
    "intelligence": "int",
    "cha": "cha",
    "charisma": "cha",
}


def register_core_tools(
    server, repository: GameRepository, *, dice_resource_uri: str | None = None
) -> None:
    """Register persistent campaign, character, snapshot, and check tools."""

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

    check_tool = (
        server.tool(meta={"ui": {"resourceUri": dice_resource_uri}})
        if dice_resource_uri
        else server.tool()
    )

    @check_tool
    async def create_check(
        campaign_id: str,
        character_id: str,
        ability: str,
        dice_spec: dict[str, int],
        difficulty: int,
        reason: str,
    ) -> dict[str, object]:
        """Create a pending check; wait for the user's Dice App roll before narrating."""
        access_token = _require_access_token()
        validated_campaign_id = _validate_uuid(campaign_id, "campaign_id")
        validated_character_id = _validate_uuid(character_id, "character_id")
        check_type = _validate_ability(ability)
        validated_dice = _validate_dice_spec(dice_spec)
        if (
            isinstance(difficulty, bool)
            or not isinstance(difficulty, int)
            or not 5 <= difficulty <= 25
        ):
            raise ValueError("difficulty must be an integer between 5 and 25")
        _validate_text(reason, "reason", 1000)
        return dict(
            await repository.create_check(
                access_token,
                validated_campaign_id,
                validated_character_id,
                check_type,
                validated_dice,
                difficulty,
                reason.strip(),
            )
        )

    @server.tool()
    async def resolve_check(check_id: str, rolls: list[int]) -> dict[str, object]:
        """Resolve a pending check from raw user rolls; server values are authoritative."""
        access_token = _require_access_token()
        validated_check_id = _validate_uuid(check_id, "check_id")
        validated_rolls = _validate_rolls(rolls)
        return dict(
            await repository.resolve_check(access_token, validated_check_id, validated_rolls)
        )


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


def _validate_ability(value: str) -> str:
    if not isinstance(value, str) or value.strip().lower() not in ABILITY_ALIASES:
        raise ValueError("ability must be str, dex, int, cha or their full names")
    return ABILITY_ALIASES[value.strip().lower()]


def _validate_dice_spec(dice_spec: Mapping[str, object]) -> dict[str, int]:
    if not isinstance(dice_spec, Mapping):
        raise ValueError("dice_spec must be an object")
    if set(dice_spec) != {"count", "sides"}:
        raise ValueError("dice_spec must contain exactly count and sides")
    count = dice_spec["count"]
    sides = dice_spec["sides"]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (count, sides)):
        raise ValueError("dice count and sides must be integers")
    if not 1 <= count <= 20 or not 2 <= sides <= 100:
        raise ValueError("dice count must be 1..20 and sides must be 2..100")
    return {"count": count, "sides": sides}


def _validate_rolls(rolls: list[int]) -> list[int]:
    if not isinstance(rolls, list) or not 1 <= len(rolls) <= 20:
        raise ValueError("rolls must be a list containing 1..20 values")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in rolls):
        raise ValueError("rolls must contain only integers")
    return list(rolls)
