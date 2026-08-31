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
  </main>
  <script>
    (() => {
      const host = window.openai;
      const byId = (id) => document.getElementById(id);
      const text = (value, fallback = "—") => value === null || value === undefined || value === "" ? fallback : String(value);

      function outputFromHost() {
        const output = host && host.toolOutput;
        if (!output || typeof output !== "object") return null;
        return output.structuredContent || output;
      }

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
      }

      render(outputFromHost());
      window.addEventListener("message", (event) => {
        if (event.data && event.data.type === "mcp-app-tool-output") render(event.data.output);
      });
    })();
  </script>
</body>
</html>"""
