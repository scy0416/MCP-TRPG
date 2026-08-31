# MCP Tools

현재 서버가 제공하는 게임 Tool의 입력·출력 경계다. 모든 게임 Tool은 인증된
사용자의 Supabase access token으로 호출되며, 권한과 게임 상태 검증은 서버와
데이터베이스에서 수행한다.

## `create_campaign`

`title`을 받아 사용자의 새 캠페인을 만든다. 캠페인 생성 이벤트도 같은
트랜잭션에서 기록한다.

## `create_character`

`campaign_id`, `name`, `stats`를 받아 캐릭터를 만든다. `stats`는 `str`, `dex`,
`int`, `cha` 키를 사용하고 값은 MVP 규칙에 따른 `0`, `1`, `2`, `3`의 순열이어야
한다. 서버가 캐릭터의 초기 HP와 생성 이벤트를 계산·기록한다.

## `get_game`

`campaign_id`에 대해 사용자가 접근할 수 있는 캠페인, 캐릭터, 현재 장면, 장면
엔티티, 인벤토리를 하나의 게임 스냅샷으로 반환한다.

## `create_check`

다음 입력으로 아직 굴리지 않은 능력 판정을 만든다.

```json
{
  "campaign_id": "…",
  "character_id": "…",
  "ability": "strength",
  "dice_spec": {"count": 1, "sides": 20},
  "difficulty": 15,
  "reason": "잠긴 문을 부순다"
}
```

`ability`는 `str`, `dex`, `int`, `cha` 또는 해당 영문 전체 이름을 사용할 수
있다. 주사위는 `count` 1~20, `sides` 2~100이며, 난이도는 5~25다. 클라이언트가
modifier를 보낼 수 없고, 서버가 캐릭터에 저장된 능력치에서 modifier를 조회해
`pending_checks`에 기록한다.

반환값은 `check_id`, 표시용 `label`, `dice`, 서버 계산 `modifier`, `difficulty`,
`reason`, `status: "pending"`을 포함한다. 생성과
`ability_check_created` 이벤트 기록은 하나의 데이터베이스 트랜잭션이다.

한 캠페인에는 동시에 하나의 `pending` 판정만 존재할 수 있다. 판정 굴림과
`pending → resolved` 전환은 다음 단계의 `resolve_check`에서 다룬다.
