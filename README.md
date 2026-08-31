# MCP-TRPG

ChatGPT 등 MCP 호스트에서 AI GM과 함께 플레이하는 TRPG 서버입니다. 현재는 가장
작은 플레이 가능한 vertical slice를 단계적으로 구현하고 있습니다.

## 현재 구현 범위

- Python 3.12 프로젝트
- MCP Python SDK v2 기반 서버
- Streamable HTTP `/mcp` 엔드포인트
- Supabase OAuth 2.1 및 audience-bound JWT 인증
- OAuth Protected Resource Metadata와 사용자 동의 화면
- 핵심 게임 Tool `create_campaign`, `create_character`, `get_game`, `create_check`
- Dice MCP App Resource `ui://trpg/dice` (create_check 결과에 연결)
- `get_server_info` MCP Tool
- 공개 liveness endpoint `GET /health`

게임 규칙은 [`docs/game-rules.md`](docs/game-rules.md)를 참고하세요.
Supabase 환경 구성은 [`docs/supabase-setup.md`](docs/supabase-setup.md)를 참고하세요.
데이터 관계와 불변조건은 [`docs/database-schema.md`](docs/database-schema.md)를 참고하세요.
데이터 접근 권한과 RLS 경계는 [`docs/database-security.md`](docs/database-security.md)를 참고하세요.
MCP 인증 구성과 운영 절차는 [`docs/authentication.md`](docs/authentication.md)를 참고하세요.
AI-facing Resource URI와 payload 경계는 [`docs/mcp-resources.md`](docs/mcp-resources.md)를 참고하세요.
MCP Tool 입력·출력과 Dice App 동작은 [`docs/mcp-tools.md`](docs/mcp-tools.md)를 참고하세요.

## 로컬 실행

Python 설치와 가상환경 구성은 `uv`가 담당합니다.

```powershell
uv sync --dev
uv run uvicorn trpg_mcp.main:app --host 127.0.0.1 --port 8000
```

실행 후 다음 주소를 사용할 수 있습니다.

- MCP: `http://127.0.0.1:8000/mcp`
- Health: `http://127.0.0.1:8000/health`
- OAuth consent: `http://127.0.0.1:8000/oauth/consent`
- Protected Resource Metadata: `http://127.0.0.1:8000/.well-known/oauth-protected-resource/mcp`

MCP Resources:

- `trpg://rules/core`
- `trpg://campaign/{campaign_id}/context`
- `trpg://campaign/{campaign_id}/scene`
- `trpg://campaign/{campaign_id}/history/recent`

## 검증

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_supabase_setup.py
.\scripts\supabase.ps1 db reset --local
.\scripts\supabase.ps1 test db --local
.\scripts\supabase.ps1 db lint --local --level warning
```

실행 중인 서버의 실제 Streamable HTTP 연결을 확인할 수 있습니다.

```powershell
uv run python scripts/smoke_http.py
```

MCP Inspector를 사용하려면 Node.js와 정상적인 `npx` 설치가 필요합니다.

```powershell
uv run mcp dev src/trpg_mcp/main.py
```
