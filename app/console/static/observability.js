// Monster Ops Console — Observability view (LLM call traces)
// Owns: app/console/static/observability.js
(function () {
  "use strict";

  var STYLE_ID = "obs-view-styles";

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    var css =
      "#obs-view{font-family:'JetBrains Mono',monospace;color:var(--text);}" +
      "#obs-view .obs-header{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px;flex-wrap:wrap;}" +
      "#obs-view .obs-title{font-size:18px;font-weight:600;letter-spacing:.3px;margin:0;}" +
      "#obs-view .obs-subtitle{color:var(--muted);font-size:12px;margin-top:4px;}" +
      "#obs-view .obs-btn{font-family:inherit;font-size:13px;background:var(--panel-2);color:var(--text);" +
        "border:1px solid var(--border);border-radius:6px;padding:8px 16px;cursor:pointer;transition:background .12s,border-color .12s;}" +
      "#obs-view .obs-btn:hover{background:var(--panel);border-color:var(--blue);}" +
      "#obs-view .obs-btn:disabled{opacity:.5;cursor:default;}" +
      "#obs-view .obs-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:20px;}" +
      "#obs-view .obs-card{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:16px 18px;}" +
      "#obs-view .obs-card-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.6px;}" +
      "#obs-view .obs-card-value{font-size:22px;font-weight:600;margin-top:8px;}" +
      "#obs-view .obs-card.accent-blue .obs-card-value{color:var(--blue);}" +
      "#obs-view .obs-card.accent-green .obs-card-value{color:var(--green);}" +
      "#obs-view .obs-card.accent-amber .obs-card-value{color:var(--amber);}" +
      "#obs-view .obs-card.accent-orange .obs-card-value{color:var(--orange);}" +
      "#obs-view .obs-table-wrap{background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden;}" +
      "#obs-view table{width:100%;border-collapse:collapse;font-size:12.5px;}" +
      "#obs-view thead th{text-align:left;color:var(--muted);font-weight:600;text-transform:uppercase;" +
        "letter-spacing:.5px;font-size:11px;padding:11px 14px;background:var(--panel-2);border-bottom:1px solid var(--border);}" +
      "#obs-view tbody td{padding:10px 14px;border-bottom:1px solid var(--border);white-space:nowrap;}" +
      "#obs-view tbody tr:last-child td{border-bottom:none;}" +
      "#obs-view tbody tr:hover{background:var(--panel-2);}" +
      "#obs-view td.num{text-align:right;font-variant-numeric:tabular-nums;}" +
      "#obs-view .obs-provider{color:var(--blue);}" +
      "#obs-view .obs-cost{color:var(--green);}" +
      "#obs-view .obs-state{background:var(--panel);border:1px solid var(--border);border-radius:8px;" +
        "padding:28px 24px;text-align:center;color:var(--muted);font-size:13px;line-height:1.6;}" +
      "#obs-view .obs-state.error{border-color:var(--red);color:var(--red);}";
    var el = document.createElement("style");
    el.id = STYLE_ID;
    el.textContent = css;
    document.head.appendChild(el);
  }

  function fmtCost(v) {
    var n = Number(v);
    if (!isFinite(n)) n = 0;
    return "$" + n.toFixed(6);
  }

  function fmtNum(v) {
    var n = Number(v);
    if (!isFinite(n)) n = 0;
    return n.toLocaleString();
  }

  // Definitions for summary cards. Each only renders if its key is present.
  var CARD_DEFS = [
    { key: "total_calls", label: "Total Calls", accent: "blue", fmt: fmtNum },
    {
      key: "total_tokens",
      label: "Total Tokens",
      accent: "amber",
      fmt: fmtNum,
      derive: function (s) {
        if (s.total_tokens != null) return s.total_tokens;
        if (s.total_prompt_tokens != null || s.total_completion_tokens != null) {
          return (s.total_prompt_tokens || 0) + (s.total_completion_tokens || 0);
        }
        return undefined;
      },
    },
    {
      key: "total_estimated_cost_usd",
      label: "Total Cost (USD)",
      accent: "green",
      fmt: fmtCost,
    },
    {
      key: "avg_latency_ms",
      label: "Avg Latency (ms)",
      accent: "orange",
      fmt: function (v) {
        return fmtNum(Math.round(Number(v) || 0));
      },
    },
  ];

  function buildCards(summary) {
    var s = summary || {};
    var cards = document.createElement("div");
    cards.className = "obs-cards";
    var any = false;

    CARD_DEFS.forEach(function (def) {
      var raw = def.derive ? def.derive(s) : s[def.key];
      if (raw === undefined || raw === null) return;
      any = true;
      var card = document.createElement("div");
      card.className = "obs-card accent-" + def.accent;
      var label = document.createElement("div");
      label.className = "obs-card-label";
      label.textContent = def.label;
      var value = document.createElement("div");
      value.className = "obs-card-value";
      value.textContent = def.fmt(raw);
      card.appendChild(label);
      card.appendChild(value);
      cards.appendChild(card);
    });

    return any ? cards : null;
  }

  function stateEl(msg, isError) {
    var d = document.createElement("div");
    d.className = "obs-state" + (isError ? " error" : "");
    d.textContent = msg;
    return d;
  }

  function buildTable(traces) {
    var wrap = document.createElement("div");
    wrap.className = "obs-table-wrap";
    var table = document.createElement("table");

    var thead = document.createElement("thead");
    var hr = document.createElement("tr");
    ["Time", "Provider", "Model", "Tokens", "Cost ($)", "Latency (ms)"].forEach(
      function (h) {
        var th = document.createElement("th");
        th.textContent = h;
        hr.appendChild(th);
      }
    );
    thead.appendChild(hr);
    table.appendChild(thead);

    var tbody = document.createElement("tbody");
    traces.forEach(function (t) {
      t = t || {};
      var tr = document.createElement("tr");

      var prompt = Number(t.prompt_tokens) || 0;
      var completion = Number(t.completion_tokens) || 0;
      var tokens = prompt + completion;

      var cells = [
        { v: window.OPS.fmtTime(t.timestamp), cls: "" },
        { v: t.provider_name, cls: "obs-provider" },
        { v: t.model, cls: "" },
        { v: fmtNum(tokens), cls: "num" },
        { v: fmtCost(t.estimated_cost_usd), cls: "num obs-cost" },
        { v: fmtNum(Math.round(Number(t.latency_ms) || 0)), cls: "num" },
      ];

      cells.forEach(function (c) {
        var td = document.createElement("td");
        if (c.cls) td.className = c.cls;
        // Values already escaped via textContent assignment below.
        td.textContent = window.OPS.esc(c.v == null ? "—" : String(c.v));
        tr.appendChild(td);
      });

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    return wrap;
  }

  function render(container) {
    injectStyles();

    var root = document.createElement("div");
    root.id = "obs-view";

    // Header
    var header = document.createElement("div");
    header.className = "obs-header";

    var titleWrap = document.createElement("div");
    var title = document.createElement("h2");
    title.className = "obs-title";
    title.textContent = "Observability — LLM Call Traces";
    var subtitle = document.createElement("div");
    subtitle.className = "obs-subtitle";
    subtitle.textContent = "Per-call tokens, latency, and estimated cost.";
    titleWrap.appendChild(title);
    titleWrap.appendChild(subtitle);

    var refreshBtn = document.createElement("button");
    refreshBtn.className = "obs-btn";
    refreshBtn.textContent = "Refresh";

    header.appendChild(titleWrap);
    header.appendChild(refreshBtn);
    root.appendChild(header);

    // Body container (re-filled on each load)
    var body = document.createElement("div");
    body.id = "obs-body";
    root.appendChild(body);

    // Mount (clean re-render)
    container.innerHTML = "";
    container.appendChild(root);

    function load() {
      refreshBtn.disabled = true;
      refreshBtn.textContent = "Loading…";
      body.innerHTML = "";

      window.OPS
        .apiFetch("/api/v1/traces?limit=100", { method: "GET" })
        .then(function (data) {
          data = data || {};
          var traces = Array.isArray(data.traces) ? data.traces : [];
          var summary = data.summary || {};

          var cards = buildCards(summary);
          if (cards) body.appendChild(cards);

          if (!traces.length) {
            body.appendChild(
              stateEl(
                "No LLM calls traced yet — traces are recorded in-memory and " +
                  "reset on restart. Use the Playground to generate some.",
                false
              )
            );
          } else {
            body.appendChild(buildTable(traces));
          }
        })
        .catch(function (err) {
          var msg =
            "Failed to load traces: " +
            (err && err.message ? err.message : String(err));
          body.appendChild(stateEl(msg, true));
        })
        .then(function () {
          refreshBtn.disabled = false;
          refreshBtn.textContent = "Refresh";
        });
    }

    refreshBtn.addEventListener("click", load);
    load();
  }

  window.VIEWS = window.VIEWS || {};
  window.VIEWS.observability = { render: render };
})();
