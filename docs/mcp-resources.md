# MCP Resource 계약

Stage 6의 Resource는 PostgreSQL row를 그대로 반환하는 API가 아니다. 서버가 인증된
사용자의 campaign 상태를 AI GM 목적에 맞게 조합한 JSON 또는 규칙 Markdown을 제공한다.

## URI 목록

| URI | MIME type | 용도 |
|---|---|---|
| `trpg://rules/core` | `text/markdown` | 판정·책임·authoritative source 핵심 규칙 |
| `trpg://campaign/{campaign_id}/context` | `application/json` | 캠페인, 캐릭터, 현재 장면, 주변 대상, 인벤토리 context |
| `trpg://campaign/{campaign_id}/scene` | `application/json` | 현재 장면과 장면 내 공개 대상 |
| `trpg://campaign/{campaign_id}/history/recent` | `application/json` | 최근 이벤트의 AI-facing 요약 |

`campaign_id`는 UUID여야 한다. 모든 campaign template resource는 MCP bearer token의
`sub`를 provider에 전달한다. provider가 membership과 row 접근을 확인하지 못하면
리소스는 반환되지 않는다.

## Payload 경계

context는 다음과 같이 의미 단위로 조합한다.

```json
{
  "campaign": {"id": "...", "title": "The Forgotten Tower", "status": "active"},
  "character": {
    "id": "...", "name": "Arin", "hp": 18, "max_hp": 24,
    "stats": {"str": 3, "dex": 2, "int": 1, "cha": 0}
  },
  "scene": {"id": "...", "name": "Old Gate", "description": "..."},
  "entities": [{"id": "...", "type": "door", "name": "Locked Door"}],
  "inventory": [{"id": "...", "name": "Potion", "quantity": 2}]
}
```

내부 소유권 식별자(`owner_id`, `user_id`)와 DB 운영 필드(`created_at`, `updated_at`)는
재귀적으로 제거한다. access token, secret, raw authorization data는 어떤 Resource에도
포함하지 않는다. 게임 Tool이 authoritative 상태를 변경하고, Resource는 그 결과를
읽기 위한 context만 제공한다.

## 구현 경계

`ResourceProvider`는 이미 권한이 적용된 snapshot을 반환하는 읽기 인터페이스다.
운영 기본값은 `SupabaseGameRepository`이며 Supabase REST/PostgREST 요청에 현재 access
token을 전달한다. 테스트는 `SnapshotResourceProvider`를 사용한다. adapter는 다음 순서를
지켜야 한다.

1. access token의 `sub`를 사용자 identity로 사용한다.
2. campaign membership을 확인하는 RLS 적용 요청으로 campaign과 관련 row를 조회한다.
3. 현재 scene, entities, character, inventory, recent events를 필요한 필드만 선택한다.
4. Resource layer에 전달할 목적별 snapshot을 만든다.

서버 프로세스 메모리는 authoritative source가 아니며, `SnapshotResourceProvider`를
production 데이터 저장소로 사용하지 않는다.

## 확인 방법

```powershell
uv run pytest tests/integration/test_server.py
```

MCP client는 `resources/list`로 static resource와 template metadata를 확인한 뒤,
인증된 상태에서 `resources/read`를 호출한다. Stage 7의 `get_game` Tool도 같은
repository context를 재사용해 자연어 Tool 응답과 Resource 응답의 의미가 갈라지지 않게 한다.
