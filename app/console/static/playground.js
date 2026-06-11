/* Monster Ops Console — Playground view
 * Two modes: "Chat" (watch the agent think) and "Tools" (invoke an MCP tool directly).
 * Self-contained vanilla JS. Registers window.VIEWS.playground.
 * Relies on the shell contract: window.OPS (apiFetch/esc/fmtTime) + :root palette vars.
 */
(function () {
  "use strict";

  // -- Inject component CSS once (guarded by element id) --------------------
  function injectStyles() {
    if (document.getElementById("pg-styles")) return;
    var css = `
.pg-wrap { display:flex; flex-direction:column; height:100%; min-height:480px;
  font-family:Inter, system-ui, sans-serif; color:var(--text); gap:14px; }
.pg-seg { display:inline-flex; background:var(--panel-2); border:1px solid var(--border);
  border-radius:9px; padding:3px; align-self:flex-start; }
.pg-seg button { background:transparent; border:0; color:var(--muted); cursor:pointer;
  padding:7px 18px; font-size:13px; font-weight:600; border-radius:6px; font-family:inherit;
  transition:background .12s, color .12s; }
.pg-seg button.active { background:var(--blue); color:#fff; }
.pg-panel { flex:1; display:flex; flex-direction:column; min-height:0; }

/* --- Chat mode --- */
.pg-convo { flex:1; overflow-y:auto; padding:6px 4px 12px; display:flex;
  flex-direction:column; gap:14px; }
.pg-empty { color:var(--muted); font-size:13px; text-align:center; margin:auto; padding:30px; }
.pg-row { display:flex; }
.pg-row.user { justify-content:flex-end; }
.pg-bubble-user { background:var(--blue); color:#fff; padding:9px 13px; border-radius:12px 12px 3px 12px;
  max-width:75%; font-size:14px; line-height:1.45; white-space:pre-wrap; word-break:break-word; }
.pg-card { background:var(--panel); border:1px solid var(--border); border-radius:12px 12px 12px 3px;
  max-width:88%; padding:13px 15px; display:flex; flex-direction:column; gap:10px; }
.pg-reply { font-size:14px; line-height:1.5; white-space:pre-wrap; word-break:break-word; }
.pg-chips { display:flex; flex-wrap:wrap; gap:7px; align-items:center; }
.pg-chip { font-size:11px; font-weight:700; letter-spacing:.3px; padding:3px 9px; border-radius:999px;
  text-transform:uppercase; border:1px solid transparent; }
.pg-chip.intent { background:rgba(68,147,248,.15); color:var(--blue); border-color:var(--blue); }
.pg-chip.guard { background:rgba(248,81,73,.16); color:var(--red); border-color:var(--red); }
.pg-pill { font-size:11px; font-weight:700; padding:3px 9px; border-radius:999px;
  display:inline-flex; gap:5px; align-items:center; }
.pg-pill.HIGH { background:rgba(63,185,80,.16); color:var(--green); border:1px solid var(--green); }
.pg-pill.MEDIUM { background:rgba(210,153,34,.16); color:var(--amber); border:1px solid var(--amber); }
.pg-pill.LOW { background:rgba(248,81,73,.16); color:var(--red); border:1px solid var(--red); }
.pg-sources { font-size:12px; color:var(--muted); display:flex; flex-direction:column; gap:3px;
  border-top:1px solid var(--border); padding-top:9px; }
.pg-sources b { color:var(--text); font-weight:600; }
.pg-sources li { margin-left:16px; }
.pg-details { border-top:1px solid var(--border); padding-top:9px; }
.pg-details summary { cursor:pointer; font-size:12px; color:var(--muted); font-weight:600;
  user-select:none; }
.pg-details summary:hover { color:var(--text); }
.pg-pre { background:var(--bg); border:1px solid var(--border); border-radius:8px; padding:10px 12px;
  margin-top:8px; font-family:'JetBrains Mono', ui-monospace, monospace; font-size:12px;
  line-height:1.5; color:var(--text); overflow-x:auto; white-space:pre; max-height:340px; }
.pg-err { color:var(--red); font-size:13px; }
.pg-loading { color:var(--muted); font-size:13px; display:flex; gap:8px; align-items:center; }
.pg-dot { width:7px; height:7px; border-radius:50%; background:var(--amber);
  animation:pg-blink 1s infinite; }
@keyframes pg-blink { 0%,100%{opacity:.3;} 50%{opacity:1;} }

/* --- Composer / inputs --- */
.pg-composer { display:flex; gap:9px; margin-top:8px; }
.pg-input { flex:1; background:var(--panel-2); border:1px solid var(--border); border-radius:9px;
  color:var(--text); font-family:inherit; font-size:14px; padding:11px 13px; resize:none; }
.pg-input:focus { outline:none; border-color:var(--blue); }
.pg-btn { background:var(--blue); color:#fff; border:0; border-radius:9px; cursor:pointer;
  font-family:inherit; font-size:13px; font-weight:600; padding:0 20px; }
.pg-btn:hover:not(:disabled) { filter:brightness(1.08); }
.pg-btn:disabled { opacity:.5; cursor:not-allowed; }

/* --- Tools mode --- */
.pg-tools { display:flex; flex-direction:column; gap:14px; flex:1; min-height:0; overflow-y:auto; }
.pg-field { display:flex; flex-direction:column; gap:6px; }
.pg-label { font-size:12px; font-weight:600; color:var(--muted); text-transform:uppercase;
  letter-spacing:.4px; }
.pg-select { background:var(--panel-2); border:1px solid var(--border); border-radius:9px;
  color:var(--text); font-family:inherit; font-size:14px; padding:10px 12px; }
.pg-select:focus { outline:none; border-color:var(--blue); }
.pg-desc { font-size:13px; color:var(--muted); line-height:1.45; min-height:18px; }
.pg-args { background:var(--bg); border:1px solid var(--border); border-radius:9px; color:var(--text);
  font-family:'JetBrains Mono', ui-monospace, monospace; font-size:13px; padding:11px 13px;
  resize:vertical; min-height:120px; line-height:1.5; }
.pg-args:focus { outline:none; border-color:var(--blue); }
.pg-result-head { font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.4px;
  display:flex; gap:9px; align-items:center; }
.pg-badge-ok { color:var(--green); }
.pg-badge-err { color:var(--red); }
`;
    var el = document.createElement("style");
    el.id = "pg-styles";
    el.textContent = css;
    document.head.appendChild(el);
  }

  // -- Small DOM helpers ----------------------------------------------------
  function h(tag, cls, text) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text != null) el.textContent = text; // textContent => safe, no HTML injection
    return el;
  }
  function pretty(obj) {
    try { return JSON.stringify(obj, null, 2); }
    catch (_e) { return String(obj); }
  }

  // ========================================================================
  // CHAT MODE
  // ========================================================================
  function renderChat(panel, state) {
    panel.textContent = "";

    var convo = h("div", "pg-convo");
    if (state.chatLog.length === 0) {
      convo.appendChild(h("div", "pg-empty",
        "Ask the concierge anything — watch its intent, confidence, sources and tool calls."));
    } else {
      state.chatLog.forEach(function (entry) { convo.appendChild(buildChatEntry(entry)); });
    }

    var composer = h("div", "pg-composer");
    var input = h("textarea", "pg-input");
    input.rows = 1;
    input.placeholder = "Message the concierge…  (Enter to send, Shift+Enter for newline)";
    var sendBtn = h("button", "pg-btn", "Send");

    function doSend() {
      var text = input.value.trim();
      if (!text || state.sending) return;
      state.sending = true;
      input.value = "";
      sendBtn.disabled = true;

      state.chatLog.push({ kind: "user", text: text });
      var loading = { kind: "loading" };
      state.chatLog.push(loading);
      renderChat(panel, state); // re-render to show user bubble + loader

      OPS.apiFetch("/chat", {
        method: "POST",
        body: { message: text, session_id: state.sessionId },
      }).then(function (data) {
        replaceEntry(state, loading, { kind: "assistant", data: data });
      }).catch(function (err) {
        replaceEntry(state, loading, { kind: "error", text: (err && err.message) || String(err) });
      }).then(function () {
        state.sending = false;
        renderChat(panel, state);
        // focus restored after re-render
        var fresh = panel.querySelector(".pg-input");
        if (fresh) fresh.focus();
      });
    }

    sendBtn.addEventListener("click", doSend);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); doSend(); }
    });

    composer.appendChild(input);
    composer.appendChild(sendBtn);
    panel.appendChild(convo);
    panel.appendChild(composer);

    // keep scrolled to newest
    convo.scrollTop = convo.scrollHeight;
  }

  function replaceEntry(state, target, replacement) {
    var i = state.chatLog.indexOf(target);
    if (i !== -1) state.chatLog.splice(i, 1, replacement);
  }

  function buildChatEntry(entry) {
    if (entry.kind === "user") {
      var row = h("div", "pg-row user");
      row.appendChild(h("div", "pg-bubble-user", entry.text));
      return row;
    }
    if (entry.kind === "loading") {
      var lrow = h("div", "pg-row");
      var card = h("div", "pg-card");
      var ld = h("div", "pg-loading");
      ld.appendChild(h("span", "pg-dot"));
      ld.appendChild(h("span", null, "Thinking…"));
      card.appendChild(ld);
      lrow.appendChild(card);
      return lrow;
    }
    if (entry.kind === "error") {
      var erow = h("div", "pg-row");
      var ecard = h("div", "pg-card");
      ecard.appendChild(h("div", "pg-err", "Error: " + entry.text));
      erow.appendChild(ecard);
      return erow;
    }
    // assistant
    return buildAssistantCard(entry.data);
  }

  function buildAssistantCard(data) {
    var row = h("div", "pg-row");
    var card = h("div", "pg-card");

    // Reply text. We build the DOM via innerHTML using OPS.esc-escaped server text,
    // satisfying the contract's "escape all server text via OPS.esc" requirement
    // (no raw innerHTML of unescaped server data).
    var reply = h("div", "pg-reply");
    reply.innerHTML = OPS.esc(data && data.reply != null ? String(data.reply) : "(no reply)");
    card.appendChild(reply);

    // Chips row: intent + confidence + guardrail
    var chips = h("div", "pg-chips");
    if (data && data.intent) {
      chips.appendChild(h("span", "pg-chip intent", String(data.intent)));
    }
    if (data && data.confidence) {
      var c = data.confidence;
      var lvl = (c.level || "").toUpperCase();
      var pill = h("span", "pg-pill " + (lvl || "LOW"));
      var pct = (typeof c.overall_score === "number")
        ? Math.round(c.overall_score * 100) + "%" : "—";
      pill.appendChild(h("span", null, lvl || "?"));
      pill.appendChild(h("span", null, pct));
      chips.appendChild(pill);
    }
    if (data && data.guardrail) {
      chips.appendChild(h("span", "pg-chip guard", "Guardrail: " + String(data.guardrail)));
    }
    if (chips.childNodes.length) card.appendChild(chips);

    // Sources
    if (data && Array.isArray(data.sources) && data.sources.length) {
      var src = h("div", "pg-sources");
      src.appendChild(h("b", null, "Sources"));
      var ul = h("ul");
      ul.style.margin = "0";
      ul.style.padding = "0";
      data.sources.forEach(function (s) {
        var label = (s && typeof s === "object") ? pretty(s) : String(s);
        ul.appendChild(h("li", null, label));
      });
      src.appendChild(ul);
      card.appendChild(src);
    }

    // Tools used (collapsible, pretty JSON) — only when non-empty
    if (data && Array.isArray(data.tools_used) && data.tools_used.length) {
      var det = h("details", "pg-details");
      det.appendChild(h("summary", null, "Tools used (" + data.tools_used.length + ")"));
      det.appendChild(h("pre", "pg-pre", pretty(data.tools_used)));
      card.appendChild(det);
    }

    // Claim verification (bonus, collapsible) when present
    if (data && data.claim_verification) {
      var cdet = h("details", "pg-details");
      cdet.appendChild(h("summary", null, "Claim verification"));
      cdet.appendChild(h("pre", "pg-pre", pretty(data.claim_verification)));
      card.appendChild(cdet);
    }

    row.appendChild(card);
    return row;
  }

  // ========================================================================
  // TOOLS MODE
  // ========================================================================
  function renderTools(panel, state) {
    panel.textContent = "";
    var wrap = h("div", "pg-tools");

    var status = h("div", "pg-desc");

    // Tool select field
    var selField = h("div", "pg-field");
    selField.appendChild(h("div", "pg-label", "Tool"));
    var select = h("select", "pg-select");
    selField.appendChild(select);
    var desc = h("div", "pg-desc");
    selField.appendChild(desc);

    // Arguments field
    var argField = h("div", "pg-field");
    argField.appendChild(h("div", "pg-label", "Arguments (JSON)"));
    var args = h("textarea", "pg-args");
    args.value = state.toolArgs || "{}";
    args.addEventListener("input", function () { state.toolArgs = args.value; });
    argField.appendChild(args);

    var callBtn = h("button", "pg-btn", "Call tool");
    callBtn.style.alignSelf = "flex-start";
    callBtn.style.padding = "10px 22px";
    callBtn.disabled = true;

    var resultBox = h("div", "pg-field");

    wrap.appendChild(status);
    wrap.appendChild(selField);
    wrap.appendChild(argField);
    wrap.appendChild(callBtn);
    wrap.appendChild(resultBox);
    panel.appendChild(wrap);

    function populateSelect(tools) {
      select.textContent = "";
      tools.forEach(function (t, idx) {
        var opt = document.createElement("option");
        opt.value = String(idx);
        opt.textContent = t.name || ("tool " + idx);
        select.appendChild(opt);
      });
      function syncDesc() {
        var t = tools[parseInt(select.value, 10)] || {};
        desc.textContent = t.description || "(no description)";
      }
      select.addEventListener("change", syncDesc);
      syncDesc();
    }

    function loadTools() {
      status.textContent = "Loading tools…";
      callBtn.disabled = true;
      OPS.apiFetch("/api/v1/mcp/tools", { method: "GET" }).then(function (data) {
        var tools = (data && Array.isArray(data.tools)) ? data.tools : [];
        state.tools = tools;
        if (!tools.length) {
          status.textContent = "No MCP tools available.";
          return;
        }
        status.textContent = tools.length + " tool" + (tools.length === 1 ? "" : "s") + " available.";
        populateSelect(tools);
        callBtn.disabled = false;
      }).catch(function (err) {
        status.textContent = "";
        resultBox.textContent = "";
        resultBox.appendChild(h("div", "pg-err",
          "Failed to load tools: " + ((err && err.message) || String(err))));
      });
    }

    function showResult(content, isError) {
      resultBox.textContent = "";
      var head = h("div", "pg-result-head");
      head.appendChild(h("span", null, "Result"));
      head.appendChild(h("span", isError ? "pg-badge-err" : "pg-badge-ok",
        isError ? "● isError: true" : "● ok"));
      resultBox.appendChild(head);

      var items = Array.isArray(content) ? content : [];
      if (!items.length) {
        resultBox.appendChild(h("pre", "pg-pre", "(empty content)"));
        return;
      }
      items.forEach(function (item) {
        var body;
        if (item && item.type === "json") {
          body = pretty(item.json);
        } else if (item && typeof item.text === "string") {
          // try to pretty-print JSON-looking text, else show raw
          try { body = pretty(JSON.parse(item.text)); }
          catch (_e) { body = item.text; }
        } else {
          body = pretty(item);
        }
        // OPS.esc per contract; <pre> textContent already prevents injection.
        resultBox.appendChild(h("pre", "pg-pre", body));
      });
    }

    callBtn.addEventListener("click", function () {
      var tools = state.tools || [];
      var t = tools[parseInt(select.value, 10)];
      if (!t) return;

      var parsed;
      try {
        parsed = JSON.parse(args.value || "{}");
      } catch (e) {
        resultBox.textContent = "";
        resultBox.appendChild(h("div", "pg-err", "Invalid JSON in arguments: " + e.message));
        return;
      }
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        resultBox.textContent = "";
        resultBox.appendChild(h("div", "pg-err", "Arguments must be a JSON object, e.g. {}"));
        return;
      }

      callBtn.disabled = true;
      callBtn.textContent = "Calling…";
      resultBox.textContent = "";
      var ld = h("div", "pg-loading");
      ld.appendChild(h("span", "pg-dot"));
      ld.appendChild(h("span", null, "Calling " + (t.name || "tool") + "…"));
      resultBox.appendChild(ld);

      OPS.apiFetch("/api/v1/mcp/call", {
        method: "POST",
        body: { name: t.name, arguments: parsed },
      }).then(function (data) {
        showResult(data && data.content, !!(data && data.isError));
      }).catch(function (err) {
        resultBox.textContent = "";
        resultBox.appendChild(h("div", "pg-err",
          "Call failed: " + ((err && err.message) || String(err))));
      }).then(function () {
        callBtn.disabled = false;
        callBtn.textContent = "Call tool";
      });
    });

    // load on entering Tools mode (fresh each render of this mode)
    if (state.tools && state.tools.length) {
      status.textContent = state.tools.length + " tool" +
        (state.tools.length === 1 ? "" : "s") + " available.";
      populateSelect(state.tools);
      callBtn.disabled = false;
    } else {
      loadTools();
    }
  }

  // ========================================================================
  // VIEW SHELL: segmented toggle + mode dispatch
  // ========================================================================
  function render(container) {
    injectStyles();
    container.textContent = "";

    // per-render-instance state (re-render cleanly each call)
    var state = {
      mode: "chat",
      sessionId: (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : "sess-" + Date.now() + "-" + Math.random().toString(16).slice(2),
      chatLog: [],
      sending: false,
      tools: null,
      toolArgs: "{}",
    };

    var wrap = h("div", "pg-wrap");

    // segmented toggle
    var seg = h("div", "pg-seg");
    var chatTab = h("button", "active", "Chat");
    var toolsTab = h("button", null, "Tools");
    seg.appendChild(chatTab);
    seg.appendChild(toolsTab);

    var panel = h("div", "pg-panel");

    function switchTo(mode) {
      state.mode = mode;
      chatTab.classList.toggle("active", mode === "chat");
      toolsTab.classList.toggle("active", mode === "tools");
      if (mode === "chat") renderChat(panel, state);
      else renderTools(panel, state);
    }

    chatTab.addEventListener("click", function () { switchTo("chat"); });
    toolsTab.addEventListener("click", function () { switchTo("tools"); });

    wrap.appendChild(seg);
    wrap.appendChild(panel);
    container.appendChild(wrap);

    switchTo("chat"); // default mode
  }

  window.VIEWS = window.VIEWS || {};
  window.VIEWS.playground = { render: render };
})();
