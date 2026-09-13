# MCP 인증

Stage 5는 Supabase Auth를 OAuth 2.1 authorization server로 사용하고 MCP-TRPG를
보호된 resource server로 구성한다. `/health`, OAuth 동의 화면 및 discovery 문서를
제외한 `/mcp` 요청은 유효한 bearer access token이 없으면 거부된다.

## 인증 흐름

1. MCP client가 `/.well-known/oauth-protected-resource/mcp`를 조회한다.
2. 문서에 표시된 Supabase issuer에서 OAuth metadata를 조회한다.
3. client가 동적 등록 후 authorization code + PKCE 흐름을 시작한다.
4. 사용자가 `/oauth/consent`에서 기존 계정으로 로그인하거나 새 계정을 만든 뒤 요청을 허용하거나 거부한다.
5. Supabase가 MCP resource URI를 `aud`로 갖는 access token을 발급한다.
6. MCP 서버가 JWKS 서명, issuer, audience, 만료, 사용자와 OAuth client claims를 모두
   검증한 뒤 요청을 처리한다.

OpenAI의 MCP 인증 안내는 OAuth 2.1, Protected Resource Metadata, 올바른 401 challenge,
PKCE와 resource/audience binding을 요구한다. 구현 기준은 다음 공식 문서다.

- [OpenAI MCP authentication](https://developers.openai.com/plugins/build/auth)
- [MCP authorization specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [Supabase MCP authentication](https://supabase.com/docs/guides/auth/oauth-server/mcp-authentication)

## 신뢰 경계

- MCP 서버는 `RS256`과 `ES256`만 허용한다. 공유 secret 기반 `HS256` token은 받지 않는다.
- JWKS의 `kid`로 공개키를 찾고 signature, `iss`, 정확한 `aud`, `exp`, `iat`를 검증한다.
- `role=authenticated`, UUID 형식의 `sub`, 비어 있지 않은 `client_id`가 필수다.
- `user_id`가 있으면 `sub`와 같아야 한다. 관리용 `service_role` token은 MCP 요청에
  사용할 수 없다.
- 검증 또는 JWKS 조회가 실패하면 인증은 fail closed된다.
- Supabase의 표준 OAuth scopes는 사용자 정보 공개 범위다. 게임 데이터 권한은 scope가
  아니라 사용자 JWT를 전달받는 Data API와 RLS가 결정한다.
- publishable key는 동의 화면에서 사용하는 공개 식별자다. secret key와 JWT private key는
  브라우저, 로그, Tool 결과 또는 Git에 포함하지 않는다.

## 환경변수

| 이름 | 로컬 기본값 | 의미 |
|---|---|---|
| `SUPABASE_URL` | `http://127.0.0.1:54321` | Supabase API base URL |
| `SUPABASE_AUTH_ISSUER` | `${SUPABASE_URL}/auth/v1` | access token의 정확한 issuer |
| `SUPABASE_JWKS_URL` | `${SUPABASE_AUTH_ISSUER}/.well-known/jwks.json` | 공개 signing keys |
| `SUPABASE_PUBLISHABLE_KEY` | 없음 | 브라우저 동의 화면 초기화에 필요 |
| `MCP_RESOURCE_URL` | `http://127.0.0.1:8000/mcp` | protected resource ID이자 token audience |

운영 URL은 모두 HTTPS여야 한다. `MCP_RESOURCE_URL`은 외부에서 접근할 실제 `/mcp`
URL과 한 글자도 다르면 안 된다.

## 로컬 실행과 확인

OAuth 설정은 Auth 컨테이너 생성 시 적용되므로 `supabase/config.toml`을 바꾼 뒤에는 stack을
재시작한다.

```powershell
.\scripts\supabase.ps1 stop
.\scripts\supabase.ps1 start
.\scripts\supabase.ps1 db reset --local
uv run uvicorn trpg_mcp.main:app --host 127.0.0.1 --port 8000
```

`supabase start` 출력의 publishable key를 untracked `.env`에만 설정한다. 다음 URL에서
설정을 확인할 수 있다.

- Protected resource: `http://127.0.0.1:8000/.well-known/oauth-protected-resource/mcp`
- Authorization metadata: `http://127.0.0.1:54321/auth/v1/.well-known/oauth-authorization-server`
- OIDC metadata: `http://127.0.0.1:54321/auth/v1/.well-known/openid-configuration`
- JWKS: `http://127.0.0.1:54321/auth/v1/.well-known/jwks.json`

현재 고정한 CLI의 로컬 gateway에서는 문서에 함께 소개된
`/.well-known/oauth-authorization-server/auth/v1` 경로가 404일 수 있다. issuer에 붙는
위 authorization metadata 경로는 같은 metadata와 DCR endpoint를 정상 제공하며,
Protected Resource Metadata는 해당 issuer를 광고한다.

## Hosted Supabase 설정

동의 화면에는 이메일·비밀번호 로그인과 회원가입이 함께 제공된다. Supabase Auth의 이메일
확인이 활성화된 환경에서는 가입 직후 세션이 발급되지 않으므로 확인 메일을 처리한 뒤 같은
화면에서 다시 로그인해야 한다.

development와 production project 각각에 다음을 별도로 적용한다.

1. Authentication > OAuth Server에서 OAuth server와 dynamic client registration을 켠다.
2. Site URL을 MCP 서버 origin으로, Authorization Path를 `/oauth/consent`로 설정한다.
3. JWT signing key를 `RS256` 또는 `ES256` 비대칭 key로 설정한다.
4. migration을 적용한 다음 해당 환경의 정확한 resource URI를 등록한다.

```sql
insert into private.mcp_auth_config (resource_uri)
values ('https://trpg.example.com/mcp')
on conflict (singleton) do update
set resource_uri = excluded.resource_uri;
```

Hosted migration은 로컬 `seed.sql`을 자동 실행하지 않으므로 4번을 생략하면 OAuth token
발급이 의도적으로 실패한다. 이어서 서버 환경의 `SUPABASE_URL`, publishable key와
`MCP_RESOURCE_URL`을 설정하고 `scripts/check_supabase_setup.py --require-remote`를 실행한다.

실제 ChatGPT 연결과 hosted redirect URI 상호운용 검증은 외부 HTTPS 배포가 준비되는
통합 단계에서 수행한다. Dynamic registration을 사용하지 않는 host는 해당 host가 제공한
redirect URI를 exact match로 별도 OAuth client에 등록한다.

## 테스트 범위

- Python unit test: 정상 token과 잘못된 signature key, issuer, audience, 만료, role,
  subject 및 algorithm 공격
- ASGI integration test: 공개 endpoint, 401 `WWW-Authenticate`, Protected Resource
  Metadata, 인증된 MCP initialize와 consent 보안 headers
- pgTAP: OAuth token audience 변경, 일반 Supabase session 보존, 권한 및 설정 누락 시
  fail-closed 동작

