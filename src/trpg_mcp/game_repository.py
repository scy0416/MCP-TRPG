"""Supabase-backed persistence boundary for core game operations."""

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken

from trpg_mcp.config import Settings
from trpg_mcp.resources import ResourceProvider


class GameRepository(ResourceProvider, Protocol):
    """Persistence operations required by the core MCP tools."""

    async def create_campaign(
        self, access_token: AccessToken, title: str
    ) -> Mapping[str, object]: ...

    async def create_character(
        self,
        access_token: AccessToken,
        campaign_id: str,
        name: str,
        stats: Mapping[str, int],
    ) -> Mapping[str, object]: ...

    async def get_game(
        self, access_token: AccessToken, campaign_id: str
    ) -> Mapping[str, object] | None: ...

    async def create_check(
        self,
        access_token: AccessToken,
        campaign_id: str,
        character_id: str,
        check_type: str,
        dice_spec: Mapping[str, int],
        difficulty: int,
        context: str,
    ) -> Mapping[str, object]: ...


class SupabaseRestError(RuntimeError):
    """Safe-to-log PostgREST error without credentials or authorization headers."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"Supabase request failed ({status_code}): {detail}")
        self.status_code = status_code
        self.detail = detail


@dataclass(slots=True)
class SupabaseRestClient:
    """Minimal async PostgREST client using the caller's access token."""

    base_url: str
    publishable_key: str
    timeout_seconds: float = 10.0

    async def request(
        self,
        *,
        table: str,
        method: str,
        access_token: AccessToken,
        query: Mapping[str, str] | None = None,
        payload: Mapping[str, object] | None = None,
        prefer: str | None = None,
    ) -> object:
        if not self.publishable_key:
            raise SupabaseRestError(503, "SUPABASE_PUBLISHABLE_KEY is not configured")
        if not access_token.token:
            raise SupabaseRestError(401, "authenticated access token is required")

        path = f"{self.base_url.rstrip('/')}/rest/v1/{table}"
        if query:
            path = f"{path}?{urlencode(query)}"
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token.token}",
            "Content-Type": "application/json",
            "apikey": self.publishable_key,
        }
        if prefer:
            headers["Prefer"] = prefer

        request = Request(path, data=body, headers=headers, method=method)
        try:
            response_body = await asyncio.to_thread(self._open, request)
        except HTTPError as error:
            detail = await asyncio.to_thread(error.read)
            raise SupabaseRestError(error.code, _safe_error_detail(detail)) from error
        except (URLError, TimeoutError, OSError) as error:
            raise SupabaseRestError(503, "Supabase is unavailable") from error

        if not response_body:
            return []
        try:
            return json.loads(response_body)
        except json.JSONDecodeError as error:
            raise SupabaseRestError(502, "Supabase returned invalid JSON") from error

    def _open(self, request: Request) -> bytes:
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read()


def _safe_error_detail(body: bytes) -> str:
    try:
        decoded = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "upstream request rejected"
    if isinstance(decoded, Mapping):
        message = decoded.get("message") or decoded.get("hint") or decoded.get("error")
        if isinstance(message, str) and len(message) <= 200:
            return message
    return "upstream request rejected"


@dataclass(slots=True)
class SupabaseGameRepository:
    """Repository that relies on Supabase RLS for caller-scoped rows."""

    settings: Settings
    client: SupabaseRestClient | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = SupabaseRestClient(
                self.settings.supabase_url, self.settings.supabase_publishable_key
            )

    async def create_campaign(self, access_token: AccessToken, title: str) -> Mapping[str, object]:
        rows = await self._request(
            table="rpc/create_campaign",
            method="POST",
            access_token=access_token,
            payload={"p_title": title},
        )
        row = _object_response(rows, "campaign creation")
        return _campaign_row(row)

    async def create_character(
        self,
        access_token: AccessToken,
        campaign_id: str,
        name: str,
        stats: Mapping[str, int],
    ) -> Mapping[str, object]:
        rows = await self._request(
            table="rpc/create_character",
            method="POST",
            access_token=access_token,
            payload={
                "p_campaign_id": campaign_id,
                "p_name": name,
                "p_str": stats["str"],
                "p_dex": stats["dex"],
                "p_int": stats["int"],
                "p_cha": stats["cha"],
            },
        )
        row = _object_response(rows, "character creation")
        return _character_row(row)

    async def get_game(
        self, access_token: AccessToken, campaign_id: str
    ) -> Mapping[str, object] | None:
        campaign_rows = await self._select(
            "campaigns",
            access_token,
            {"select": "id,title,status,current_scene_id", "id": f"eq.{campaign_id}", "limit": "1"},
        )
        if not campaign_rows:
            return None

        campaign = _campaign_row(_first_object(campaign_rows, "campaign lookup"))
        character_rows = await self._select(
            "characters",
            access_token,
            {
                "select": "id,name,hp,max_hp,str,dex,int,cha,status",
                "campaign_id": f"eq.{campaign_id}",
                "user_id": f"eq.{access_token.subject}",
                "limit": "1",
            },
        )
        character = _character_row(character_rows[0]) if character_rows else None
        scene = None
        entities: list[Mapping[str, object]] = []
        if campaign.get("current_scene_id"):
            scene_rows = await self._select(
                "scenes",
                access_token,
                {
                    "select": "id,name,description,state",
                    "id": f"eq.{campaign['current_scene_id']}",
                    "campaign_id": f"eq.{campaign_id}",
                    "limit": "1",
                },
            )
            if scene_rows:
                scene = _scene_row(scene_rows[0])
                entity_rows = await self._select(
                    "entities",
                    access_token,
                    {
                        "select": "id,entity_type,name,description,state",
                        "campaign_id": f"eq.{campaign_id}",
                        "scene_id": f"eq.{scene['id']}",
                        "order": "created_at.asc",
                    },
                )
                entities = [_entity_row(row) for row in entity_rows]

        inventory: list[Mapping[str, object]] = []
        if character:
            inventory_rows = await self._select(
                "inventory_items",
                access_token,
                {
                    "select": "id,item_type,name,quantity,state",
                    "character_id": f"eq.{character['id']}",
                    "order": "created_at.asc",
                },
            )
            inventory = [_inventory_row(row) for row in inventory_rows]

        return {
            "campaign": campaign,
            "character": character,
            "scene": scene,
            "entities": entities,
            "inventory": inventory,
        }

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
        result = await self._request(
            table="rpc/create_check",
            method="POST",
            access_token=access_token,
            payload={
                "p_campaign_id": campaign_id,
                "p_character_id": character_id,
                "p_check_type": check_type,
                "p_dice_spec": dict(dice_spec),
                "p_difficulty": difficulty,
                "p_context": context,
            },
        )
        return _check_row(_object_response(result, "check creation"))

    async def get_campaign_context(
        self, campaign_id: str, subject: str
    ) -> Mapping[str, object] | None:
        access_token = get_access_token()
        if access_token is None or access_token.subject != subject:
            return None
        return await self.get_game(access_token, campaign_id)

    async def get_scene(self, campaign_id: str, subject: str) -> Mapping[str, object] | None:
        access_token = get_access_token()
        if access_token is None or access_token.subject != subject:
            return None
        game = await self.get_game(access_token, campaign_id)
        return game.get("scene") if game else None

    async def get_recent_history(
        self, campaign_id: str, subject: str
    ) -> list[Mapping[str, object]] | None:
        access_token = get_access_token()
        if access_token is None or access_token.subject != subject:
            return None
        rows = await self._select(
            "game_events",
            access_token,
            {
                "select": "id,event_type,payload,created_at",
                "campaign_id": f"eq.{campaign_id}",
                "order": "created_at.desc",
                "limit": "20",
            },
        )
        return [
            {key: row.get(key) for key in ("id", "event_type", "payload", "created_at")}
            for row in rows
        ]

    async def _select(
        self,
        table: str,
        access_token: AccessToken,
        query: Mapping[str, str],
    ) -> list[Mapping[str, object]]:
        result = await self._request(
            table=table, method="GET", access_token=access_token, query=query
        )
        if not isinstance(result, list):
            raise SupabaseRestError(502, f"Supabase returned an invalid {table} response")
        return [row for row in result if isinstance(row, Mapping)]

    async def _request(self, **kwargs: Any) -> object:
        assert self.client is not None
        return await self.client.request(**kwargs)


def _first_object(value: object, operation: str) -> Mapping[str, object]:
    if isinstance(value, list) and value and isinstance(value[0], Mapping):
        return value[0]
    raise SupabaseRestError(502, f"Supabase returned no row for {operation}")


def _object_response(value: object, operation: str) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return _first_object(value, operation)


def _campaign_row(row: Mapping[str, object]) -> dict[str, object]:
    return {key: row.get(key) for key in ("id", "title", "status", "current_scene_id")}


def _character_row(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "hp": row.get("hp"),
        "max_hp": row.get("max_hp"),
        "stats": {key: row.get(key) for key in ("str", "dex", "int", "cha")},
        "status": row.get("status") or {},
    }


def _scene_row(row: Mapping[str, object]) -> dict[str, object]:
    return {key: row.get(key) for key in ("id", "name", "description", "state")}


def _entity_row(row: Mapping[str, object]) -> dict[str, object]:
    return {key: row.get(key) for key in ("id", "entity_type", "name", "description", "state")}


def _inventory_row(row: Mapping[str, object]) -> dict[str, object]:
    return {key: row.get(key) for key in ("id", "item_type", "name", "quantity", "state")}


def _check_row(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "check_id": row.get("id"),
        "label": f"{str(row.get('check_type', '')).upper()} Check",
        "dice": row.get("dice_spec"),
        "modifier": row.get("modifier"),
        "difficulty": row.get("difficulty"),
        "reason": row.get("context"),
        "status": row.get("status"),
    }
