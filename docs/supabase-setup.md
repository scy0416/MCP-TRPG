# Supabase 환경 구성

## 고정 결정

- 로컬 개발은 Supabase CLI `2.116.0`을 사용한다.
- hosted project는 서울 `ap-northeast-2`에 생성한다.
- 개발과 운영 project를 `mcp-trpg-dev`, `mcp-trpg-prod`로 분리한다.
- 로컬 schema와 seed는 `supabase/` 아래에서 버전 관리한다.
- 새 `sb_publishable_...` 및 `sb_secret_...` API key 체계를 사용한다.
- 일반 사용자 요청은 publishable key와 사용자 access token을 사용한다.
- secret key는 RLS를 우회하므로 명시적인 관리 작업 외에는 사용하지 않는다.

`anon`과 `service_role`은 legacy key이므로 새 코드와 환경변수 이름에 사용하지 않는다.

## 로컬 준비

Supabase CLI는 공식 안정판 `2.116.0`으로 고정한다. 프로젝트 루트에서 다음 결과가
나와야 한다.

```text
supabase --version
2.116.0
```

로컬 전체 stack에는 Docker 호환 runtime이 필요하다. Docker 엔진이 실행된 상태에서:

```powershell
supabase start
supabase db reset --local
```

`db reset`은 로컬 DB를 제거하고 migration 및 seed로 다시 생성하는 명령이다. hosted
project에 대해서는 `--linked`를 사용하지 않는다.

현재 Stage 2 구성은 Postgres, Auth, Data API와 Studio만을 대상으로 한다. MVP에 필요하지
않은 Realtime, Storage, Edge Runtime 및 Analytics는 비활성화했다.

## Hosted project 생성

Supabase Dashboard 또는 Management API에서 다음 두 project를 생성한다.

| 환경 | 이름 | 리전 | 용도 |
|---|---|---|---|
| Development | `mcp-trpg-dev` | Seoul (`ap-northeast-2`) | 개발 및 통합 테스트 |
| Production | `mcp-trpg-prod` | Seoul (`ap-northeast-2`) | 승인된 배포만 사용 |

두 project는 서로 다른 DB password와 API key를 사용한다. project ref, password, access
token 또는 secret key를 Git에 커밋하지 않는다.

CLI 인증 후 개발 project만 로컬 저장소에 연결한다.

```powershell
supabase login
supabase link --project-ref <development-project-ref>
```

Production project 연결과 migration 반영은 CI/CD Stage에서 별도 자격 증명으로 한다.
개발자가 로컬에서 production DB를 reset하거나 직접 migration하지 않는다.

## 환경변수

`.env.example`을 `.env`로 복사하고 실제 값을 입력한다. `.env`는 Git에서 제외된다.

| 이름 | 필수 시점 | 설명 |
|---|---|---|
| `SUPABASE_URL` | Stage 3 | project API URL |
| `SUPABASE_PUBLISHABLE_KEY` | Stage 5 | RLS를 우회하지 않는 공개 key; OAuth 동의 화면에서 사용 |
| `SUPABASE_PROJECT_REF` | remote CLI 작업 | 개발 project reference |
| `SUPABASE_SECRET_KEY` | 관리 작업만 | RLS를 우회하는 backend secret |
| `SUPABASE_AUTH_ISSUER` | Stage 5, 선택 | 기본값은 `${SUPABASE_URL}/auth/v1` |
| `SUPABASE_JWKS_URL` | Stage 5, 선택 | 기본값은 issuer의 JWKS endpoint |
| `MCP_RESOURCE_URL` | Stage 5 | 외부에서 접근할 정확한 HTTPS `/mcp` URL |

secret key는 MCP App UI, 로그, Tool 응답 또는 클라이언트 JavaScript로 전달하지 않는다.

## 검증

커밋된 로컬 설정만 확인한다.

```powershell
uv run python scripts/check_supabase_setup.py
```

hosted project 환경변수까지 확인한다. 검증기는 값 자체를 출력하지 않는다.

```powershell
uv run python scripts/check_supabase_setup.py --require-remote
```

Hosted 통합 작업 전 완료 조건:

- 개발 project가 `ap-northeast-2`에 생성되어 있다.
- production project 또는 별도의 production 생성 일정이 확정되어 있다.
- 로컬 저장소는 개발 project에만 연결되어 있다.
- `.env`에 개발 URL, publishable key와 project ref가 있다.
- Docker 기반 로컬 stack 또는 hosted development DB 중 하나에 연결할 수 있다.

OAuth server, token audience와 MCP 환경 구성은
[`authentication.md`](authentication.md)를 참고한다.
