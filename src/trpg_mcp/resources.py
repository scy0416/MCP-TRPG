"""Purpose-built MCP resources for the AI GM context."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver import Context

RULES_CORE = """# MCP-TRPG 핵심 규칙

- 장면과 저장된 상태를 먼저 확인한다.
- 결과가 불확실하고 실패가 의미 있는 경우에만 능력 판정을 만든다.
- 판정은 d20 + 저장된 능력치 modifier이며, total이 DC 이상이면 성공한다.
- d20 원값은 사용자가 Dice UI에서 굴린 뒤 서버에 제출한다. AI GM은 대신 굴리지 않는다.
- 서버 응답으로 확정된 결과만 서술하고, 상태 변경은 MCP Tool을 통해서만 수행한다.
- 일반 서술 → 필요할 때 `create_check` → 사용자 Roll → `resolve_check` → 결과 서술 순서를 지킨다.
- AI나 UI가 보낸 modifier, DC, total, success, HP 또는 아이템 변경값은 authoritative하지 않다.
- Supabase PostgreSQL이 캠페인, 캐릭터, 장면, 아이템과 이벤트의 authoritative source다.
"""


class ResourceProvider(Protocol):
    """Read campaign state after enforcing the caller's identity and membership."""

    async def get_campaign_context(
        self, campaign_id: str, subject: str
    ) -> Mapping[str, object] | None: ...

    async def get_scene(self, campaign_id: str, subject: str) -> Mapping[str, object] | None: ...

    async def get_recent_history(
        self, campaign_id: str, subject: str
    ) -> list[Mapping[str, object]] | None: ...


@dataclass(slots=True)
class SnapshotResourceProvider:
    """Deterministic provider used by local development and tests."""

    snapshots: dict[str, dict[str, object]] = field(default_factory=dict)

    def put(self, campaign_id: str, subject: str, snapshot: Mapping[str, object]) -> None:
        self.snapshots[f"{subject}:{campaign_id}"] = dict(snapshot)

    async def get_campaign_context(
        self, campaign_id: str, subject: str
    ) -> Mapping[str, object] | None:
        snapshot = self.snapshots.get(f"{subject}:{campaign_id}")
        value = snapshot.get("context") if snapshot else None
        return value if isinstance(value, Mapping) else None

    async def get_scene(self, campaign_id: str, subject: str) -> Mapping[str, object] | None:
        snapshot = self.snapshots.get(f"{subject}:{campaign_id}")
        value = snapshot.get("scene") if snapshot else None
        return value if isinstance(value, Mapping) else None

    async def get_recent_history(
        self, campaign_id: str, subject: str
    ) -> list[Mapping[str, object]] | None:
        snapshot = self.snapshots.get(f"{subject}:{campaign_id}")
        value = snapshot.get("history") if snapshot else None
        return value if isinstance(value, list) else None


def register_resources(server, provider: ResourceProvider) -> None:
    """Register static rules and authenticated campaign resource templates."""

    @server.resource(
        "trpg://rules/core",
        name="trpg_rules_core",
        title="MCP-TRPG 핵심 규칙",
        description="AI GM이 따라야 하는 최소 게임 규칙과 책임 경계",
        mime_type="text/markdown",
    )
    def rules_core() -> str:
        return RULES_CORE

    @server.resource(
        "trpg://campaign/{campaign_id}/context",
        name="campaign_context",
        title="Campaign context",
        description="현재 캠페인, 캐릭터, 장면, 주변 대상과 인벤토리의 목적별 context",
        mime_type="application/json",
    )
    async def campaign_context(campaign_id: str, ctx: Context) -> str:
        subject = _authenticated_subject()
        snapshot = await provider.get_campaign_context(_validate_campaign_id(campaign_id), subject)
        return _json_or_not_found(snapshot, "campaign context")

    @server.resource(
        "trpg://campaign/{campaign_id}/scene",
        name="campaign_scene",
        title="Current scene",
        description="현재 장면과 장면에 존재하는 공개 대상",
        mime_type="application/json",
    )
    async def campaign_scene(campaign_id: str, ctx: Context) -> str:
        subject = _authenticated_subject()
        snapshot = await provider.get_scene(_validate_campaign_id(campaign_id), subject)
        return _json_or_not_found(snapshot, "current scene")

    @server.resource(
        "trpg://campaign/{campaign_id}/history/recent",
        name="campaign_history_recent",
        title="Recent campaign history",
        description="최근 게임 이벤트의 AI-facing 요약",
        mime_type="application/json",
    )
    async def campaign_history_recent(campaign_id: str, ctx: Context) -> str:
        subject = _authenticated_subject()
        events = await provider.get_recent_history(_validate_campaign_id(campaign_id), subject)
        return _json_or_not_found(events, "recent history")


def _authenticated_subject() -> str:
    access_token = get_access_token()
    if access_token is None or not access_token.subject:
        raise PermissionError("authenticated MCP resource access is required")
    return access_token.subject


def _validate_campaign_id(campaign_id: str) -> str:
    try:
        return str(UUID(campaign_id))
    except ValueError as error:
        raise ValueError("campaign_id must be a UUID") from error


def _json_or_not_found(value: object, resource_name: str) -> str:
    if value is None:
        raise LookupError(f"{resource_name} is not available to this user")
    return json.dumps(_sanitize(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sanitize(value: object) -> object:
    """Keep JSON data and drop database identity/internal columns recursively."""
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize(item)
            for key, item in value.items()
            if str(key) not in {"owner_id", "user_id", "created_at", "updated_at"}
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"resource value is not JSON serializable: {type(value).__name__}")
