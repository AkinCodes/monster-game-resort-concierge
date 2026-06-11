(function () {
  "use strict";

  var STYLE_ID = "evals-view-styles";
  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    var s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = [
      ".ev-root{padding:22px;max-width:1100px;color:var(--text);font-family:Inter,system-ui,sans-serif;}",
      ".ev-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;}",
      ".ev-head h2{margin:0;font-size:16px;}",
      ".ev-sub{color:var(--muted);font-size:12px;margin-bottom:18px;}",
      ".ev-btn{background:var(--blue);color:#fff;border:0;border-radius:6px;padding:7px 12px;font-weight:600;font-size:13px;cursor:pointer;}",
      ".ev-section{margin:22px 0 8px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);}",
      ".ev-cards{display:flex;flex-wrap:wrap;gap:12px;}",
      ".ev-card{flex:1 1 150px;min-width:140px;background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px 16px;}",
      ".ev-card .v{font-size:1.5rem;font-weight:800;line-height:1.1;}",
      ".ev-card .l{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:4px;}",
      ".ev-card .s{font-size:11px;color:var(--muted);margin-top:3px;}",
      ".ev-card.good .v{color:var(--green);} .ev-card.warn .v{color:var(--amber);} .ev-card.bad .v{color:var(--red);} .ev-card.mono .v{font-family:'JetBrains Mono',monospace;}",
      ".ev-bars{display:flex;flex-direction:column;gap:8px;margin-top:6px;}",
      ".ev-bar{display:grid;grid-template-columns:160px 1fr 70px;align-items:center;gap:10px;font-size:12.5px;}",
      ".ev-bar .track{height:8px;background:var(--panel-2);border-radius:5px;overflow:hidden;}",
      ".ev-bar .fill{height:100%;background:var(--blue);}",
      ".ev-bar .pct{color:var(--muted);text-align:right;font-family:'JetBrains Mono',monospace;font-size:11.5px;}",
      ".ev-table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:4px;}",
      ".ev-table th,.ev-table td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border);}",
      ".ev-table th{color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.4px;}",
      ".ev-table td.n{font-family:'JetBrains Mono',monospace;}",
      ".ev-table tr.best td{background:rgba(63,185,80,.10);}",
      ".ev-table tr.best td:first-child::after{content:' \\2605';color:var(--green);}",
      ".ev-exp{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px;}",
      ".ev-exp .name{flex:1;}",
      ".ev-chip{font-size:11px;font-weight:600;padding:2px 9px;border-radius:999px;border:1px solid var(--border);}",
      ".ev-chip.HIGH{background:rgba(63,185,80,.14);color:var(--green);border-color:rgba(63,185,80,.4);}",
      ".ev-chip.MEDIUM{background:rgba(210,153,34,.14);color:var(--amber);border-color:rgba(210,153,34,.4);}",
      ".ev-chip.LOW{background:rgba(248,81,73,.14);color:var(--red);border-color:rgba(248,81,73,.4);}",
      ".ev-exp .sc{font-family:'JetBrains Mono',monospace;color:var(--muted);font-size:11.5px;width:54px;text-align:right;}",
      ".ev-exp .mt{width:20px;text-align:center;}",
      ".ev-muted{color:var(--muted);padding:20px 0;}",
      ".ev-error{color:var(--red);border:1px solid rgba(248,81,73,.4);background:rgba(248,81,73,.08);border-radius:8px;padding:12px 14px;}",
    ].join("");
    document.head.appendChild(s);
  }

  var OPS = window.OPS;
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function pct(x) { return (x == null) ? "—" : (Math.round(x * 1000) / 10) + "%"; }
  function fixed(x, d) { return (x == null) ? "—" : Number(x).toFixed(d == null ? 3 : d); }

  function card(value, label, sub, tone) {
    var c = el("div", "ev-card" + (tone ? " " + tone : ""));
    c.appendChild(el("div", "v", value));
    c.appendChild(el("div", "l", label));
    if (sub != null) c.appendChild(el("div", "s", sub));
    return c;
  }
  function section(title) { return el("div", "ev-section", title); }

  function renderEndToEnd(body, r) {
    if (!r) return;
    body.appendChild(section("End-to-end eval (judge harness)"));
    var cards = el("div", "ev-cards");
    var rateTone = r.pass_rate >= 0.7 ? "good" : (r.pass_rate >= 0.4 ? "warn" : "bad");
    cards.appendChild(card(pct(r.pass_rate), "Pass rate", (r.passed != null ? r.passed + "/" + r.total + " cases" : null), rateTone));
    cards.appendChild(card(pct(r.tool_selection_accuracy), "Tool selection", null, "mono"));
    cards.appendChild(card(pct(r.avg_retrieval_relevance), "Retrieval relevance", null, "mono"));
    if (r.avg_hallucination_score != null) cards.appendChild(card(fixed(r.avg_hallucination_score, 2), "Avg confidence", "hallucination score", "mono"));
    body.appendChild(cards);

    var cat = r.category_results || {};
    var keys = Object.keys(cat);
    if (keys.length) {
      var bars = el("div", "ev-bars");
      bars.style.marginTop = "14px";
      keys.forEach(function (k) {
        var c = cat[k] || {};
        var row = el("div", "ev-bar");
        row.appendChild(el("div", null, k.replace(/_/g, " ")));
        var track = el("div", "track"); var fill = el("div", "fill");
        fill.style.width = Math.round((c.pass_rate || 0) * 100) + "%";
        if (c.pass_rate >= 0.7) fill.style.background = "var(--green)";
        else if (c.pass_rate < 0.4) fill.style.background = "var(--red)";
        track.appendChild(fill); row.appendChild(track);
        row.appendChild(el("div", "pct", pct(c.pass_rate) + "  (" + (c.passed || 0) + "/" + (c.total || 0) + ")"));
        bars.appendChild(row);
      });
      body.appendChild(bars);
    }
  }

  function renderRetrieval(body, m) {
    if (!m) return;
    body.appendChild(section("Retrieval quality"));
    var cards = el("div", "ev-cards");
    cards.appendChild(card(fixed(m.mrr), "MRR", (m.num_queries != null ? m.num_queries + " queries" : null), "mono"));
    cards.appendChild(card(fixed(m.recall_at_5), "Recall@5", null, "mono"));
    cards.appendChild(card(fixed(m.recall_at_10), "Recall@10", null, "mono"));
    cards.appendChild(card(fixed(m.precision_at_5), "Precision@5", null, "mono"));
    body.appendChild(cards);
  }

  function renderAblation(body, a) {
    if (!a || typeof a !== "object") return;
    var configs = Object.keys(a);
    if (!configs.length) return;
    body.appendChild(section("Retrieval ablation (per config)"));
    // find best avg_mrr
    var best = null, bestV = -1;
    configs.forEach(function (k) { var v = (a[k] || {}).avg_mrr; if (typeof v === "number" && v > bestV) { bestV = v; best = k; } });
    var table = el("table", "ev-table");
    var thead = el("tr");
    ["Config", "MRR", "P@5", "Latency (ms)", "Results"].forEach(function (h) { thead.appendChild(el("th", null, h)); });
    table.appendChild(thead);
    configs.forEach(function (k) {
      var c = a[k] || {};
      var tr = el("tr", k === best ? "best" : null);
      tr.appendChild(el("td", null, k));
      tr.appendChild(el("td", "n", fixed(c.avg_mrr)));
      tr.appendChild(el("td", "n", fixed(c.avg_precision_at_5)));
      tr.appendChild(el("td", "n", c.avg_latency_ms != null ? fixed(c.avg_latency_ms, 2) : "—"));
      tr.appendChild(el("td", "n", c.avg_result_count != null ? fixed(c.avg_result_count, 1) : "—"));
      table.appendChild(tr);
    });
    body.appendChild(table);
  }

  function renderHallucination(body, h) {
    if (!h || !h.experiments) return;
    body.appendChild(section("Hallucination detector experiments"));
    var sub = el("div", "ev-sub");
    sub.textContent = (h.num_matched != null ? h.num_matched + "/" + h.num_experiments + " expected levels matched" : "") +
      (h.timestamp ? "  ·  " + OPS.fmtTime(h.timestamp) : "");
    body.appendChild(sub);
    var names = Object.keys(h.experiments);
    names.forEach(function (name) {
      var ex = h.experiments[name] || {};
      var row = el("div", "ev-exp");
      row.appendChild(el("div", "name", name));
      var lvl = String(ex.level || "").toUpperCase();
      if (lvl) { var chip = el("span", "ev-chip " + lvl, lvl); row.appendChild(chip); }
      row.appendChild(el("div", "sc", ex.score != null ? Number(ex.score).toFixed(3) : ""));
      var mt = el("div", "mt", ex.match ? "✓" : "✗");
      mt.style.color = ex.match ? "var(--green)" : "var(--red)";
      row.appendChild(mt);
      body.appendChild(row);
    });
  }

  function render(container) {
    injectStyles();
    container.innerHTML = "";
    var root = el("div", "ev-root");
    var head = el("div", "ev-head");
    head.appendChild(el("h2", null, "Evals — Offline Quality Scoreboard"));
    var btn = el("button", "ev-btn", "Refresh");
    head.appendChild(btn);
    root.appendChild(head);
    root.appendChild(el("div", "ev-sub", "Pre-computed offline eval reports (read-only). Run the eval scripts to refresh the numbers."));
    var body = el("div", "ev-body");
    root.appendChild(body);
    container.appendChild(root);

    function load() {
      body.innerHTML = "";
      body.appendChild(el("div", "ev-muted", "Loading eval reports…"));
      OPS.apiFetch("/console/evals").then(function (resp) {
        body.innerHTML = "";
        var e = (resp && resp.evals) || {};
        renderEndToEnd(body, e.eval_report);
        renderRetrieval(body, e.retrieval_metrics);
        renderAblation(body, e.retrieval_ablation);
        renderHallucination(body, e.hallucination);
        if (!e.eval_report && !e.retrieval_metrics && !e.retrieval_ablation && !e.hallucination) {
          body.appendChild(el("div", "ev-muted", "No eval reports found in reports/. Run the eval scripts (evals/, scripts/eval_harness.py) to populate them."));
        }
      }).catch(function (err) {
        body.innerHTML = "";
        body.appendChild(el("div", "ev-error", "Failed to load evals: " + (err && err.message || err)));
      });
    }
    btn.addEventListener("click", load);
    load();
  }

  window.VIEWS = window.VIEWS || {};
  window.VIEWS.evals = { render: render };
})();
