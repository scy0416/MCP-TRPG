"""Minimal browser consent UI for the Supabase OAuth authorization flow."""

from base64 import b64encode
from secrets import token_urlsafe

from starlette.responses import HTMLResponse, Response

from trpg_mcp.config import Settings

SUPABASE_JS_VERSION = "2.106.2"


def consent_response(settings: Settings) -> Response:
    """Return the public consent page without exposing server credentials."""
    if not settings.supabase_publishable_key:
        return HTMLResponse(
            "OAuth consent is not configured: SUPABASE_PUBLISHABLE_KEY is missing.",
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )

    nonce = token_urlsafe(24)
    supabase_url = _base64(settings.supabase_url)
    publishable_key = _base64(settings.supabase_publishable_key)
    html = _CONSENT_HTML.replace("__NONCE__", nonce)
    html = html.replace("__SUPABASE_URL_B64__", supabase_url)
    html = html.replace("__SUPABASE_KEY_B64__", publishable_key)

    connect_source = settings.supabase_url
    content_security_policy = "; ".join(
        (
            "default-src 'none'",
            f"script-src 'nonce-{nonce}' https://cdn.jsdelivr.net",
            f"connect-src {connect_source}",
            "style-src 'unsafe-inline'",
            "img-src 'self' data:",
            "base-uri 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        )
    )
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": content_security_policy,
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _base64(value: str) -> str:
    return b64encode(value.encode()).decode("ascii")


_CONSENT_HTML = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MCP-TRPG 연결 승인</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      background: #15131a; color: #f6f1ff;
    }}
    main {{
      width: min(32rem, calc(100% - 2rem)); padding: 2rem;
      border: 1px solid #51475f; border-radius: 1rem; background: #211c29;
    }}
    h1 {{ margin-top: 0; font-size: 1.5rem; }}
    label {{ display: grid; gap: .4rem; margin: 1rem 0; }}
    input {{ padding: .75rem; border: 1px solid #6f627f; border-radius: .5rem; font: inherit; }}
    button {{
      padding: .7rem 1rem; border: 0; border-radius: .5rem;
      font: inherit; cursor: pointer;
    }}
    .actions {{ display: flex; gap: .75rem; margin-top: 1.5rem; }}
    .approve {{ background: #8b5cf6; color: white; }}
    .deny {{ background: #4b4356; color: white; }}
    .error {{ color: #ff9b9b; white-space: pre-wrap; }}
    [hidden] {{ display: none !important; }}
  </style>
</head>
<body>
  <main>
    <h1>MCP-TRPG 연결 승인</h1>
    <p id="status">인증 요청을 확인하고 있습니다.</p>
    <p id="error" class="error" role="alert"></p>

    <form id="login" hidden>
      <p id="auth-mode-description">승인하려면 먼저 Supabase 계정으로 로그인하세요.</p>
      <label id="display-name-field" hidden>표시 이름
        <input id="display-name" type="text" autocomplete="name" maxlength="80">
      </label>
      <label>이메일 <input id="email" type="email" autocomplete="email" required></label>
      <label>비밀번호
        <input id="password" type="password" autocomplete="current-password" required>
      </label>
      <label id="password-confirm-field" hidden>비밀번호 확인
        <input id="password-confirm" type="password" autocomplete="new-password" minlength="8">
      </label>
      <div class="actions">
        <button id="submit-auth" class="approve" type="submit">로그인</button>
        <button id="switch-auth" class="deny" type="button">회원가입</button>
      </div>
    </form>

    <section id="consent" hidden>
      <p><strong id="client-name"></strong>에서 다음 TRPG 데이터 접근을 요청합니다.</p>
      <ul>
        <li>사용자 프로필</li>
        <li>참여 중인 캠페인과 캐릭터</li>
        <li>게임 진행 상태 및 Tool 실행</li>
      </ul>
      <p>OAuth 범위: <span id="scopes"></span></p>
      <div class="actions">
        <button id="approve" class="approve" type="button">허용</button>
        <button id="deny" class="deny" type="button">거부</button>
      </div>
    </section>
  </main>

  <script type="module" nonce="__NONCE__">
    import {{ createClient }} from
      "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@{SUPABASE_JS_VERSION}/+esm";

    const decode = (value) => new TextDecoder().decode(
      Uint8Array.from(atob(value), char => char.charCodeAt(0))
    );
    const supabase = createClient(decode("__SUPABASE_URL_B64__"), decode("__SUPABASE_KEY_B64__"));
    const authorizationId = new URLSearchParams(window.location.search).get("authorization_id");
    const status = document.querySelector("#status");
    const errorBox = document.querySelector("#error");
    const loginForm = document.querySelector("#login");
    const authModeDescription = document.querySelector("#auth-mode-description");
    const displayNameField = document.querySelector("#display-name-field");
    const displayName = document.querySelector("#display-name");
    const passwordConfirmField = document.querySelector("#password-confirm-field");
    const passwordConfirm = document.querySelector("#password-confirm");
    const submitAuth = document.querySelector("#submit-auth");
    const switchAuth = document.querySelector("#switch-auth");
    const consent = document.querySelector("#consent");
    let authMode = "login";

    function fail(message) {{
      status.hidden = true;
      errorBox.textContent = message;
    }}

    function setAuthMode(mode) {{
      authMode = mode;
      const isSignup = mode === "signup";
      authModeDescription.textContent = isSignup
        ? "새 Supabase 계정을 만든 뒤 연결을 승인하세요."
        : "승인하려면 먼저 Supabase 계정으로 로그인하세요.";
      displayNameField.hidden = !isSignup;
      displayName.required = false;
      passwordConfirmField.hidden = !isSignup;
      passwordConfirm.required = isSignup;
      document.querySelector("#password").minLength = isSignup ? 8 : 0;
      submitAuth.textContent = isSignup ? "회원가입" : "로그인";
      switchAuth.textContent = isSignup ? "로그인으로 돌아가기" : "회원가입";
      document.querySelector("#password").autocomplete = isSignup
        ? "new-password"
        : "current-password";
      errorBox.textContent = "";
    }}

    async function loadConsent() {{
      errorBox.textContent = "";
      if (!authorizationId) {{
        fail("authorization_id가 없습니다.");
        return;
      }}

      const {{ data: userData }} = await supabase.auth.getUser();
      if (!userData.user) {{
        status.textContent = "로그인이 필요합니다.";
        loginForm.hidden = false;
        return;
      }}

      loginForm.hidden = true;
      const {{ data, error }} = await supabase.auth.oauth.getAuthorizationDetails(authorizationId);
      if (error || !data) {{
        fail(error?.message ?? "유효하지 않은 인증 요청입니다.");
        return;
      }}
      if (!("authorization_id" in data)) {{
        window.location.assign(data.redirect_url);
        return;
      }}

      document.querySelector("#client-name").textContent = data.client?.name ?? "MCP Client";
      document.querySelector("#scopes").textContent = data.scope?.trim() || "기본 사용자 접근";
      status.hidden = true;
      consent.hidden = false;
    }}

    loginForm.addEventListener("submit", async (event) => {{
      event.preventDefault();
      const email = document.querySelector("#email").value;
      const password = document.querySelector("#password").value;
      if (authMode === "signup") {{
        if (password !== passwordConfirm.value) {{
          fail("비밀번호가 일치하지 않습니다.");
          return;
        }}
        const {{ data, error }} = await supabase.auth.signUp({{
          email,
          password,
          options: {{ data: {{ display_name: displayName.value.trim() }} }}
        }});
        if (error) {{
          fail(error.message);
          loginForm.hidden = false;
          return;
        }}
        if (!data.session) {{
          status.hidden = false;
          status.textContent = "가입이 완료되었습니다. 이메일 인증을 마친 뒤 로그인하세요.";
          errorBox.textContent = "";
          setAuthMode("login");
          return;
        }}
        await loadConsent();
        return;
      }}

      const {{ error }} = await supabase.auth.signInWithPassword({{ email, password }});
      if (error) {{
        fail(error.message);
        loginForm.hidden = false;
        return;
      }}
      await loadConsent();
    }});

    switchAuth.addEventListener(
      "click", () => setAuthMode(authMode === "login" ? "signup" : "login")
    );

    async function decide(decision) {{
      document.querySelector("#approve").disabled = true;
      document.querySelector("#deny").disabled = true;
      const {{ data, error }} = decision === "approve"
        ? await supabase.auth.oauth.approveAuthorization(authorizationId)
        : await supabase.auth.oauth.denyAuthorization(authorizationId);
      if (error || !data?.redirect_url) {{
        fail(error?.message ?? "승인 결과를 처리하지 못했습니다.");
        return;
      }}
      window.location.assign(data.redirect_url);
    }}

    document.querySelector("#approve").addEventListener("click", () => decide("approve"));
    document.querySelector("#deny").addEventListener("click", () => decide("deny"));
    await loadConsent();
  </script>
</body>
</html>
"""
