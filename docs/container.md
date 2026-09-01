# Container 실행

이 서비스는 Python 3.12와 Uvicorn을 포함한 최소 Docker 이미지로 실행할 수 있다.
컨테이너는 Cloud Run이 주입하는 `PORT`를 사용하고 `0.0.0.0`에 바인딩한다.

## 로컬 빌드와 실행

```powershell
docker build -t mcp-trpg:local .
docker run --rm -p 8080:8080 `
  -e SUPABASE_URL=http://host.docker.internal:54321 `
  -e SUPABASE_PUBLISHABLE_KEY=local-publishable-key `
  -e MCP_RESOURCE_URL=http://127.0.0.1:8080/mcp `
  mcp-trpg:local
```

Health 응답을 확인한다.

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

실제 hosted 환경에서는 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`,
`SUPABASE_AUTH_ISSUER`, `SUPABASE_JWKS_URL`, `MCP_RESOURCE_URL`을 Secret Manager
또는 Cloud Run 환경변수로 주입한다. 이미지에는 credential을 포함하지 않는다.

## Cloud Run 계약

- 프로세스는 `0.0.0.0:$PORT`에서 수신한다.
- 공개 liveness 경로는 `GET /health`다.
- 게임 상태와 인증 정보는 컨테이너 파일시스템이나 메모리에 저장하지 않는다.
- Cloud Run revision 간 공유되어야 하는 값은 Supabase에 저장한다.
