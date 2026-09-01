"""MCP App HTML for rolling a pending ability check."""

# The embedded HTML/CSS/JavaScript is intentionally kept as one portable resource.
# ruff: noqa: E501

DICE_RESOURCE_URI = "ui://trpg/dice"

DICE_APP_HTML = r"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MCP-TRPG Dice</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; }
    body { margin: 0; background: #171717; color: #f5f5f5; }
    main { box-sizing: border-box; max-width: 420px; margin: 0 auto; padding: 24px; }
    h1 { margin: 0 0 8px; font-size: 1.35rem; }
    #reason { min-height: 2.5em; color: #bdbdbd; }
    .dice { display: grid; place-items: center; min-height: 150px; margin: 18px 0; border: 1px solid #444; border-radius: 16px; background: #242424; }
    #roll-value { font-size: 4rem; font-weight: 800; }
    button { width: 100%; border: 0; border-radius: 10px; padding: 13px 16px; background: #f0b429; color: #171717; font-weight: 800; font-size: 1rem; cursor: pointer; }
    button:disabled { cursor: wait; opacity: .55; }
    .facts { display: flex; justify-content: space-between; margin-top: 18px; color: #d5d5d5; }
    .result { margin-top: 18px; text-align: center; font-weight: 800; letter-spacing: .08em; }
    .success { color: #5ee28b; }
    .failure { color: #ff7474; }
    .error { margin-top: 14px; color: #ff9c9c; font-size: .9rem; }
  </style>
</head>
<body>
  <main aria-live="polite">
    <h1 id="label">Ability Check</h1>
    <p id="reason">판정 정보를 불러오는 중…</p>
    <section class="dice" aria-label="주사위 결과"><span id="roll-value">🎲</span></section>
    <button id="roll" type="button" disabled>ROLL</button>
    <div class="facts"><span id="modifier">Modifier —</span><span id="difficulty">DC —</span></div>
    <div id="result" class="result"></div>
    <div id="error" class="error" role="alert"></div>
  </main>
  <script>
    (() => {
      let check = null;
      const byId = (id) => document.getElementById(id);

      // MCP Apps views communicate with the host over JSON-RPC postMessage.
      // The legacy host bridge is not available in Claude's MCP Apps sandbox.
      const parentWindow = window.parent;
      const pending = new Map();
      let nextRequestId = 1;
      let initialized = false;
      let hostCapabilities = {};

      function send(message) {
        parentWindow.postMessage({ jsonrpc: "2.0", ...message }, "*");
      }

      function request(method, params, timeoutMs = 5000) {
        const id = nextRequestId++;
        return new Promise((resolve, reject) => {
          const timer = setTimeout(() => {
            pending.delete(id);
            reject(new Error("호스트 응답 시간이 초과됐습니다."));
          }, timeoutMs);
          pending.set(id, { resolve, reject, timer });
          send({ id, method, params });
        });
      }

      function outputFromHost(output) {
        if (!output || typeof output !== "object") return null;
        return output.structuredContent || output;
      }

      function handleMessage(event) {
        if (event.source !== parentWindow || !event.data || event.data.jsonrpc !== "2.0") return;
        const message = event.data;
        if (message.id !== undefined && pending.has(message.id)) {
          const callback = pending.get(message.id);
          pending.delete(message.id);
          clearTimeout(callback.timer);
          if (message.error) callback.reject(new Error(message.error.message || "호스트 요청에 실패했습니다."));
          else callback.resolve(message.result);
          return;
        }
        if (message.method === "ui/notifications/tool-result") {
          setCheck(outputFromHost(message.params));
        }
      }

      window.addEventListener("message", handleMessage);

      function setCheck(value) {
        if (!value || typeof value !== "object") return;
        check = value;
        byId("label").textContent = value.label || "Ability Check";
        byId("reason").textContent = value.reason || "";
        const dice = value.dice || {};
        byId("roll").textContent = `ROLL ${dice.count || 1}d${dice.sides || 20}`;
        byId("modifier").textContent = `${value.label || "Check"} ${Number(value.modifier) >= 0 ? "+" : ""}${value.modifier}`;
        byId("difficulty").textContent = `DC ${value.difficulty}`;
        byId("roll").disabled = value.status !== "pending";
      }

      function secureRoll(sides) {
        const limit = 0x100000000 - (0x100000000 % sides);
        const values = new Uint32Array(1);
        do { crypto.getRandomValues(values); } while (values[0] >= limit);
        return (values[0] % sides) + 1;
      }

      async function resolve(rolls) {
        // Only the check id and raw rolls cross the UI/server boundary.
        if (!initialized) throw new Error("MCP App 연결이 아직 완료되지 않았습니다.");
        return request("tools/call", { name: "resolve_check", arguments: { check_id: check.check_id, rolls } });
      }

      async function reportToChat(resolved) {
        if (!resolved || typeof resolved !== "object") return;
        const rolls = Array.isArray(resolved.rolls) ? resolved.rolls.join(", ") : "—";
        const modifier = Number(resolved.modifier) >= 0 ? `+${resolved.modifier}` : String(resolved.modifier);
        const outcome = resolved.success ? "성공" : "실패";
        const text = [
          "[MCP-TRPG 판정 결과]",
          `${resolved.label || "능력 판정"}: ${outcome}`,
          `주사위: ${rolls} · 보정치: ${modifier} · 합계: ${resolved.total} · DC: ${resolved.difficulty}`,
          `사유: ${resolved.reason || "없음"}`,
        ].join("\\n");
        // A tool call made by a View is returned to the View only. Send the
        // authoritative result to the host so the model can continue in chat.
        if (hostCapabilities.message) {
          try {
            await request("ui/message", { role: "user", content: [{ type: "text", text }] });
            return;
          } catch (error) {
            if (!hostCapabilities.updateModelContext) throw error;
          }
        }
        if (hostCapabilities.updateModelContext) {
          await request("ui/update-model-context", { content: [{ type: "text", text }] });
          return;
        }
        throw new Error("이 Claude 호스트는 채팅 메시지 전달을 지원하지 않습니다.");
      }

      async function roll() {
        if (!check) return;
        const dice = check.dice || { count: 1, sides: 20 };
        const rolls = Array.from({ length: dice.count }, () => secureRoll(dice.sides));
        const rawTotal = rolls.reduce((sum, value) => sum + value, 0);
        const total = rawTotal + Number(check.modifier || 0);
        byId("roll-value").textContent = rolls.length === 1 ? `🎲 ${rolls[0]}` : `🎲 ${rawTotal}`;
        byId("result").textContent = `TOTAL ${total} · DC ${check.difficulty}`;
        byId("result").className = `result ${total >= Number(check.difficulty) ? "success" : "failure"}`;
        byId("roll").disabled = true;
        try {
          const response = await resolve(rolls);
          const resolved = response && (response.structuredContent || response);
          if (resolved && resolved.outcome) {
            byId("result").textContent = resolved.outcome.toUpperCase();
            // Do not block the Roll button on a host chat acknowledgement.
            // Some Claude clients process ui/message asynchronously.
            void reportToChat(resolved).catch((error) => {
              byId("error").textContent = error instanceof Error
                ? `판정은 완료됐지만 채팅 전달에 실패했습니다: ${error.message}`
                : "판정은 완료됐지만 채팅 전달에 실패했습니다.";
            });
          }
        } catch (error) {
          byId("error").textContent = error instanceof Error ? error.message : "판정 확정에 실패했습니다.";
          byId("roll").disabled = false;
        }
      }

      byId("roll").addEventListener("click", roll);

      async function connect() {
        try {
          const result = await request("ui/initialize", {
            protocolVersion: "2026-01-26",
            appInfo: { name: "MCP-TRPG Dice", version: "0.1.0" },
            appCapabilities: {},
          });
          hostCapabilities = result && result.hostCapabilities ? result.hostCapabilities : {};
          send({ method: "ui/notifications/initialized", params: {} });
          initialized = true;
        } catch (error) {
          byId("error").textContent = error instanceof Error ? error.message : "MCP App 연결에 실패했습니다.";
        }
      }

      connect();
    })();
  </script>
</body>
</html>"""
