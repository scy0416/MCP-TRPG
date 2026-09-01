"""MCP App HTML for displaying the authenticated game snapshot."""

# The embedded HTML/CSS/JavaScript is intentionally kept as one portable resource.
# ruff: noqa: E501

GAME_RESOURCE_URI = "ui://trpg/game"

GAME_APP_HTML = r"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MCP-TRPG Game</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; }
    body { margin: 0; background: #171717; color: #f5f5f5; }
    main { box-sizing: border-box; max-width: 520px; margin: 0 auto; padding: 22px; }
    h1, h2, p { margin-top: 0; }
    h1 { margin-bottom: 4px; font-size: 1.45rem; }
    h2 { margin-bottom: 8px; font-size: 1rem; color: #f0b429; }
    .status { color: #aaa; font-size: .85rem; }
    .panel { margin-top: 16px; padding: 16px; border: 1px solid #3d3d3d; border-radius: 14px; background: #242424; }
    .scene-description { color: #d0d0d0; line-height: 1.45; }
    .character-head { display: flex; justify-content: space-between; align-items: baseline; }
    .hp { color: #ff9c9c; font-weight: 700; }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 14px; }
    .stat { padding: 8px 4px; border-radius: 8px; background: #303030; text-align: center; }
    .stat strong { display: block; font-size: 1.15rem; }
    .stat small { color: #aaa; }
    ul { margin: 0; padding-left: 20px; color: #d0d0d0; }
    li + li { margin-top: 6px; }
    .empty { color: #999; }
    #choices { display: grid; gap: 8px; }
    .choice { border: 0; border-radius: 9px; padding: 11px 13px; background: #f0b429; color: #171717; text-align: left; font: inherit; font-weight: 700; cursor: pointer; }
    .choice small { display: block; margin-top: 3px; color: #5a4308; font-weight: 500; }
    .choice:disabled { cursor: wait; opacity: .55; }
  </style>
</head>
<body>
  <main aria-live="polite">
    <h1 id="campaign">MCP-TRPG</h1>
    <div id="campaign-status" class="status">게임 상태를 불러오는 중…</div>
    <section class="panel">
      <h2 id="scene-name">Current Scene</h2>
      <p id="scene-description" class="scene-description"></p>
    </section>
    <section class="panel">
      <div class="character-head"><h2 id="character-name">Character</h2><span id="hp" class="hp"></span></div>
      <div id="stats" class="stats"></div>
    </section>
    <section class="panel"><h2>Nearby</h2><ul id="entities"></ul></section>
    <section class="panel"><h2>Inventory</h2><ul id="inventory"></ul></section>
    <section id="choices-panel" class="panel" hidden><h2>Choices</h2><div id="choices"></div><p id="choice-status" class="status"></p></section>
  </main>
  <script>
    (() => {
      const byId = (id) => document.getElementById(id);
      const text = (value, fallback = "—") => value === null || value === undefined || value === "" ? fallback : String(value);
      const parentWindow = window.parent;
      const pending = new Map();
      let nextRequestId = 1;

      function send(message) {
        parentWindow.postMessage({ jsonrpc: "2.0", ...message }, "*");
      }

      function request(method, params) {
        const id = nextRequestId++;
        return new Promise((resolve, reject) => {
          pending.set(id, { resolve, reject });
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
          if (message.error) callback.reject(new Error(message.error.message || "호스트 요청에 실패했습니다."));
          else callback.resolve(message.result);
          return;
        }
        if (message.method === "ui/notifications/tool-result") render(outputFromHost(message.params));
      }

      window.addEventListener("message", handleMessage);

      function listItems(element, values, render) {
        element.replaceChildren();
        if (!Array.isArray(values) || values.length === 0) {
          const empty = document.createElement("li");
          empty.className = "empty";
          empty.textContent = "없음";
          element.append(empty);
          return;
        }
        values.forEach((value) => {
          const item = document.createElement("li");
          item.textContent = render(value);
          element.append(item);
        });
      }

      function choiceValues(game) {
        const scene = game.scene || {};
        const state = scene.state && typeof scene.state === "object" ? scene.state : {};
        const choices = game.choices || scene.choices || state.choices;
        return Array.isArray(choices) ? choices : [];
      }

      function choiceLabel(choice) {
        return typeof choice === "string" ? choice : text(choice && (choice.label || choice.title), "선택");
      }

      function choiceDescription(choice) {
        return choice && typeof choice === "object" ? text(choice.description, "") : "";
      }

      async function choose(choice, button) {
        const label = choiceLabel(choice);
        const description = choiceDescription(choice);
        const message = description ? `${label} — ${description}` : label;
        button.disabled = true;
        byId("choice-status").textContent = "선택을 채팅에 전달하는 중…";
        try {
          await request("ui/message", {
            role: "user",
            content: [{ type: "text", text: `[MCP-TRPG 선택] ${message}` }],
          });
          byId("choice-status").textContent = `선택됨: ${label}`;
        } catch (error) {
          button.disabled = false;
          byId("choice-status").textContent = error instanceof Error
            ? `선택 전달에 실패했습니다: ${error.message}`
            : "선택 전달에 실패했습니다.";
        }
      }

      function renderChoices(game) {
        const choices = choiceValues(game);
        const panel = byId("choices-panel");
        const container = byId("choices");
        container.replaceChildren();
        panel.hidden = choices.length === 0;
        byId("choice-status").textContent = "";
        choices.forEach((choice) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "choice";
          const label = choiceLabel(choice);
          button.append(document.createTextNode(label));
          const choiceDescriptionText = choiceDescription(choice);
          if (choiceDescriptionText) {
            const description = document.createElement("small");
            description.textContent = choiceDescriptionText;
            button.append(description);
          }
          button.addEventListener("click", () => choose(choice, button));
          container.append(button);
        });
      }

      function render(game) {
        if (!game || typeof game !== "object") return;
        const campaign = game.campaign || {};
        const scene = game.scene || {};
        const character = game.character || {};
        const stats = character.stats || {};
        byId("campaign").textContent = text(campaign.title, "Campaign");
        byId("campaign-status").textContent = `상태: ${text(campaign.status)}`;
        byId("scene-name").textContent = text(scene.name, "현재 장면 없음");
        byId("scene-description").textContent = text(scene.description, "장면 설명 없음");
        byId("character-name").textContent = text(character.name, "캐릭터 없음");
        byId("hp").textContent = character.hp === undefined ? "" : `HP ${character.hp} / ${character.max_hp}`;
        byId("stats").replaceChildren();
        ["str", "dex", "int", "cha"].forEach((ability) => {
          const stat = document.createElement("div");
          stat.className = "stat";
          stat.innerHTML = `<strong>${text(stats[ability])}</strong><small>${ability.toUpperCase()}</small>`;
          byId("stats").append(stat);
        });
        listItems(byId("entities"), game.entities, (entity) => `${text(entity.name)}${entity.entity_type ? ` · ${entity.entity_type}` : ""}`);
        listItems(byId("inventory"), game.inventory, (item) => `${text(item.name)} × ${text(item.quantity, "0")}`);
        renderChoices(game);
      }

      async function connect() {
        try {
          await request("ui/initialize", {
            protocolVersion: "2026-01-26",
            appInfo: { name: "MCP-TRPG Game", version: "0.1.0" },
            appCapabilities: {},
          });
          send({ method: "ui/notifications/initialized", params: {} });
        } catch (error) {
          byId("campaign-status").textContent = error instanceof Error ? error.message : "MCP App 연결에 실패했습니다.";
        }
      }

      connect();
    })();
  </script>
</body>
</html>"""
