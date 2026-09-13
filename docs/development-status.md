# 개발 현황 및 운영 가이드

MCP-TRPG를 다른 환경에서 이어서 개발하거나 현재 배포 상태를 확인할 때 필요한 기준을 정리한 문서다. 비밀번호, JWT secret, Supabase secret key는 이 문서나 Git에 기록하지 않는다.

## 현재 상태

| 영역 | 상태 | 내용 |
|---|---|---|
| 서버 | 완료 | Python 3.12, MCP Python SDK 2.1.1, Streamable HTTP /mcp |
| 인증 | 완료 | Supabase OAuth 2.1, Protected Resource Metadata, JWT/JWKS, PKCE 동의 흐름 |
| 게임 데이터 | 완료 | 캠페인·캐릭터·게임 스냅샷·판정 결과를 Supabase와 RLS로 관리 |
| MCP Tool | 완료 | get_server_info, create_campaign, create_character, get_game, create_check, resolve_check |
| MCP App | 완료 | ui://trpg/dice, ui://trpg/game 및 표준 MCP Apps bridge |
| 앱 상호작용 | 완료 | 주사위 결과·선택지를 host chat/context로 전달하고 capability가 없으면 non-blocking fallback |
| 컨테이너/배포 | 완료 | Docker, Artifact Registry, Cloud Run 및 /health 확인 |
| 다음 개발 대상 | 예정 | 선택지 실행을 게임 상태 변경과 연결하고 move/interact/use_item action Tool 확장 |

세부사항은 [MCP Tool 문서](mcp-tools.md), [Resource 문서](mcp-resources.md), [게임 규칙](game-rules.md), [인증 문서](authentication.md), [컨테이너 문서](container.md)를 참고한다.

## Git 및 워크트리

개발은 codex/development 워크트리에서 진행하고, 검토가 끝난 단계만 main에 병합한다.

```powershell
git clone https://github.com/scy0416/MCP-TRPG.git
Set-Location MCP-TRPG
git fetch origin
git worktree add .worktrees/development -b codex/development origin/codex/development
Set-Location .worktrees/development
```

커밋은 Conventional Commits 형식을 사용한다. 예: `feat: add action tool`, `fix: validate dice input`, `docs: update deployment guide`. 단계마다 테스트·lint 후 커밋하고, 병합 전 `git status --short --branch`로 변경 범위를 확인한다.

## 필요한 환경

- Git
- Python 3.12.x (프로젝트 범위: >=3.12,<3.13)
- `uv` (의존성 및 가상환경)
- Docker Desktop
- Google Cloud CLI (`gcloud`) 및 `trpg-mcp-507214` 프로젝트 권한
- 선택: Supabase CLI (로컬 stack), Node.js와 `npx` (MCP Inspector)

```powershell
uv sync --dev
```

로컬 환경변수는 추적되지 않는 `.env`에 작성하고 [`.env.example`](../.env.example)을 시작점으로 사용한다. 운영 secret은 Cloud Run 환경변수 또는 Secret Manager로 주입한다.

## 로컬 실행 및 검증

```powershell
uv run uvicorn trpg_mcp.main:app --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/health
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run python scripts/smoke_http.py
```

Supabase 로컬 stack:

```powershell
.\scripts\supabase.ps1 start
.\scripts\supabase.ps1 db reset --local
.\scripts\supabase.ps1 test db --local
.\scripts\supabase.ps1 db lint --local --level warning
```

MCP Inspector:

```powershell
uv run mcp dev src/trpg_mcp/main.py
```

## Docker

```powershell
docker build -t mcp-trpg:local .
docker run --rm -p 8080:8080 `
  -e SUPABASE_URL=http://host.docker.internal:54321 `
  -e SUPABASE_PUBLISHABLE_KEY=local-publishable-key `
  -e MCP_RESOURCE_URL=http://127.0.0.1:8080/mcp `
  mcp-trpg:local
Invoke-RestMethod http://127.0.0.1:8080/health
```

컨테이너는 Cloud Run이 주입하는 `PORT`와 `0.0.0.0`에 바인딩한다. 상태는 컨테이너 파일시스템에 저장하지 않고 Supabase에 저장한다.

## 현재 배포 환경

| 항목 | 값 |
|---|---|
| GCP 프로젝트 | `trpg-mcp-507214` |
| Cloud Run 리전 | `asia-northeast3` |
| Cloud Run 서비스 | `trpg-mcp` |
| MCP endpoint | https://trpg-mcp-x7434ynfta-du.a.run.app/mcp |
| Health endpoint | https://trpg-mcp-x7434ynfta-du.a.run.app/health |
| Artifact Registry | `asia-northeast3-docker.pkg.dev/trpg-mcp-507214/trpg-mcp/server` |
| 최근 배포 태그 | `signup-20260912` |
| 최근 revision | `trpg-mcp-00009-457` |

현재 서비스는 유휴 시 0개까지 scale-to-zero하도록 설정되어 있다. 배포 후 health endpoint가 `{"status":"ok","service":"MCP-TRPG","version":"0.1.0"}`를 반환하는지 확인한다.

```powershell
gcloud auth login
gcloud config set project trpg-mcp-507214
gcloud auth configure-docker asia-northeast3-docker.pkg.dev
docker build -t asia-northeast3-docker.pkg.dev/trpg-mcp-507214/trpg-mcp/server:<tag> .
docker push asia-northeast3-docker.pkg.dev/trpg-mcp-507214/trpg-mcp/server:<tag>
gcloud run deploy trpg-mcp `
  --image asia-northeast3-docker.pkg.dev/trpg-mcp-507214/trpg-mcp/server:<tag> `
  --region asia-northeast3 `
  --project trpg-mcp-507214
Invoke-RestMethod https://trpg-mcp-x7434ynfta-du.a.run.app/health
```

Terraform 리소스 정의는 [Terraform README](../infra/terraform/README.md)를 참고한다. `terraform.tfstate`, 실제 `terraform.tfvars`, secret 값은 커밋하지 않는다.

## Supabase 운영 설정

Hosted Supabase URL은 https://hvozttnklfzxsfdubyhe.supabase.co 이다. Auth의 OAuth Server와 Dynamic Client Registration을 활성화하고 Site URL 및 Authorization Path(`/oauth/consent`)를 서버와 일치시킨다. `private.mcp_auth_config`에는 실제 MCP resource URI를 한 건 등록한다.

```sql
insert into private.mcp_auth_config (resource_uri)
values ('https://trpg-mcp-x7434ynfta-du.a.run.app/mcp')
on conflict (singleton) do update
set resource_uri = excluded.resource_uri;
```

서버의 `MCP_RESOURCE_URL`, Supabase `resource_uri`, OAuth token의 `aud`는 한 글자까지 같아야 한다. 설정 확인:

```powershell
uv run python scripts/check_supabase_setup.py --require-remote
```

## 문제 해결 체크리스트

1. `GET /health`가 200인지 확인한다.
2. `/mcp` 경로가 endpoint에 포함됐는지 확인한다.
3. `MCP_RESOURCE_URL`, `resource_uri`, token `aud`가 동일한지 확인한다.
4. host가 MCP Apps bridge와 `ui/notifications/tool-result`를 지원하는지 확인한다.
5. 앱 전달 방식은 host capability에 따라 chat message 또는 model-context fallback으로 달라질 수 있다.
6. 원격 브랜치는 `git fetch origin; git log --oneline --all -5`로 확인한다.
