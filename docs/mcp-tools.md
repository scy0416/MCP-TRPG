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

`create_check` 결과는 `ui://trpg/dice` MCP App으로 표시된다. App은 Web Crypto로
원시 주사위 값만 생성하고, `resolve_check` 호출 시 `check_id`와 `rolls`만 보낸다.
modifier, 난이도, 성공 여부와 같은 서버 계산값은 UI가 확정 데이터로 전송하지
않는다. 서버는 `resolve_check`에서 이 값을 다시 계산한다.

한 캠페인에는 동시에 하나의 `pending` 판정만 존재할 수 있다. 판정 굴림과
`pending → resolved` 전환은 `resolve_check`에서 다룬다.

## `resolve_check`

Dice App은 `check_id`와 사용자가 실제로 굴린 원시 `rolls` 배열만 제출한다. 서버는
저장된 주사위 규격·modifier·난이도를 다시 읽어 total과 성공 여부를 계산하고,
판정 상태와 `ability_check_resolved` 이벤트를 하나의 트랜잭션으로 확정한다.
이미 해결된 `check_id`를 재전송하면 최초 확정 결과를 반환하며 상태를 중복 변경하지
않는다.

## AI GM 실행 순서

AI GM은 현재 context를 먼저 읽고, 안전하고 확정적인 행동은 바로 서술한다. 결과가
불확실하고 실패가 의미 있는 행동일 때만 `create_check`를 호출한다. 그 뒤에는
사용자가 Dice App에서 Roll할 때까지 결과를 예측하지 않고 기다린다. `resolve_check`가
반환한 서버 확정 결과를 받은 뒤에만 성공·실패와 다음 상황을 서술한다.
