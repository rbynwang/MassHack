/* Commonwatt demo: replays the recorded day (app/data/demo.js, written by `uv run commonwatt-demo`). */
(function () {
  const D = window.COMMONWATT;
  if (!D) { document.body.innerHTML = "<p style='padding:24px'>Run <code>uv run commonwatt-demo</code> first.</p>"; return; }
  const $ = (id) => document.getElementById(id);
  const S = D.summary, A = D.ask, W = A.window;
  const fmt = (x, d = 0) => Number(x).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d });
  const hourLab = (h) => `${(h + 11) % 12 + 1} ${h < 12 ? "AM" : "PM"}`;
  const KIND_ORDER = ["large_building", "small_business", "public_institution", "household"];
  const KIND_COLOR = { large_building: "#79c0ff", small_business: "#f2cc60", public_institution: "#d2a8ff", household: "#7ee787" };
  const byId = Object.fromEntries(D.members.map((m) => [m.id, m]));

  $("meta").innerHTML = `<b>${D.commons}</b> · ${D.day} (ISO-NE peak day)<br>Grid ask: reduce <b>${fmt(A.kw)} kW</b>,
    ${D.window_label}, at <b>$${A.price_usd_per_kwh.toFixed(2)}/kWh</b><br>Model tool: ${D.tool}`;

  // ------------------------------------------------------------------ network view
  const svg = $("net"), NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs, parent = svg) => { const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]); parent.appendChild(e); return e; };
  const pos = { coordinator: [300, 215], grid: [70, 70], registry: [70, 360], ledger: [70, 215] };
  const ordered = D.members.slice().sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind));
  ordered.forEach((m, i) => {
    const a = -Math.PI / 2 + (i + 0.5) * (2 * Math.PI / ordered.length) * 0.92 + 0.12;
    pos[m.id] = [430 + 190 * Math.cos(a) * 0.95, 215 + 190 * Math.sin(a)];
  });
  const edgeLayer = el("g", {});
  const nodes = {};
  const node = (id, label, sub, r, color, hidden) => {
    const g = el("g", { class: "node", transform: `translate(${pos[id][0]},${pos[id][1]})`, opacity: hidden ? 0 : 1 });
    const c = el("circle", { r, fill: "#0d1117", stroke: color, "stroke-width": 2 }, g);
    const ring = el("circle", { r: r + 4, fill: "none", stroke: "transparent", "stroke-width": 2, "stroke-dasharray": "3 2" }, g);
    const t = el("text", { y: r + 12, "text-anchor": "middle" }, g); t.textContent = label;
    if (sub) { const s = el("text", { y: r + 22, "text-anchor": "middle", class: "sub" }, g); s.textContent = sub; }
    nodes[id] = { g, c, ring, color };
  };
  node("grid", "Grid agent", "ISO-NE", 20, "#f2cc60");
  node("registry", "Registry", "agent cards", 16, "#39c5cf");
  node("ledger", "Ledger", "signed receipts", 16, "#bc8cff");
  node("coordinator", "Coordinator", "one per commons", 26, "#e6edf3");
  ordered.forEach((m) => node(m.id, m.id, m.kind_label.split(" ")[0].toLowerCase(), 11, KIND_COLOR[m.kind], true));

  const nodeOf = (id) => (id || "").replace(/^guard:/, "");
  function flash(from, to, color, dashed) {
    const a = pos[nodeOf(from)], b = pos[nodeOf(to)];
    if (!a || !b) return;
    const line = el("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: color, "stroke-width": 2.2,
      "stroke-dasharray": dashed ? "5 4" : "", opacity: 0.95 }, edgeLayer);
    setTimeout(() => line.setAttribute("opacity", 0.18), 500);
  }
  function mark(id, color, fill) {
    const n = nodes[nodeOf(id)]; if (!n) return;
    n.c.setAttribute("stroke", color); if (fill) n.c.setAttribute("fill", fill);
  }

  // ------------------------------------------------------------------ log replay
  const classify = (e) => {
    if (e.type === "response") {
      if (e.text.startsWith("Accept")) return "accept";
      if (e.text.startsWith("Counter")) return "counter";
      if (e.text.startsWith("Decline")) return "decline";
      if (e.text.startsWith("Blocked")) return "blocked";
      if (e.text.startsWith("Pooled")) return "pooled";
    }
    return { agent_card: "join", ask: "ask", offer: "offer", request: "request", assignment: "assignment",
             receipt: "receipt" }[e.type] || e.type;
  };
  const COLOR = { request: "#4ea1ff", accept: "#3fb950", counter: "#d29922", decline: "#f85149", blocked: "#f85149",
                  receipt: "#bc8cff", join: "#39c5cf", ask: "#f2cc60", pooled: "#f2cc60", offer: "#6e7681",
                  assignment: "#3fb950" };
  const log = D.log;
  let idx = 0, timer = null, showNetwork = false;

  function apply(e) {
    const k = classify(e);
    const li = document.createElement("li"); li.className = k;
    const who = e.to ? `${e.from} → ${e.to}` : e.from;
    li.innerHTML = `<span class="t">${e.t}</span><span class="who">${who}</span>${e.text}`;
    $("log").appendChild(li); $("log").scrollTop = $("log").scrollHeight;
    if (k === "join") { const n = nodes[e.from]; if (n) n.g.setAttribute("opacity", 1); flash(e.from, "registry", COLOR.join); }
    else if (e.to) flash(e.from, e.to, COLOR[k] || "#6e7681", k === "offer" || k === "receipt");
    if (k === "accept") mark(e.from, COLOR.accept, "#0f2a17");
    if (k === "counter") mark(e.from, COLOR.counter, "#2e2410");
    if (k === "decline") mark(e.from, COLOR.decline, "#2a1515");
    if (k === "blocked") { mark(e.from, COLOR.blocked, "#2a1515"); nodes[nodeOf(e.from)].ring.setAttribute("stroke", COLOR.blocked); }
    if (k === "private") nodes[nodeOf(e.from)].ring.setAttribute("stroke", "#8b98a5");
    if (k === "receipt") { mark(e.to, COLOR.receipt); flash(e.from, "ledger", COLOR.receipt, true); }
    if (k === "pooled" && !showNetwork) { showNetwork = true; drawChart(); }
    beatsFor(e, k);
  }
  function step() { if (idx < log.length) apply(log[idx++]); else stop(); }
  function play() { stop(); timer = setInterval(step, 620 - Number($("speed").value)); $("play").textContent = "❚❚ Pause"; }
  function stop() { if (timer) clearInterval(timer); timer = null; $("play").textContent = "▶ Play the day"; }
  $("play").onclick = () => (timer ? stop() : play());
  $("step").onclick = () => { stop(); step(); };
  $("all").onclick = () => { stop(); while (idx < log.length) apply(log[idx++]); };
  $("reset").onclick = () => { location.hash = ""; location.reload(); };
  if (location.hash === "#all") setTimeout(() => $("all").onclick(), 0);
  $("speed").oninput = () => { if (timer) play(); };

  // ------------------------------------------------------------------ demo beats
  const BEATS = ["1 · The network forms", "2 · Alone: spike together", "3 · Together: negotiation",
                 "4 · Live join", "5 · Receipts"];
  $("beats").innerHTML = BEATS.map((b, i) => `<span class="beat" id="beat${i}">${b}</span>`).join("");
  const on = (i) => { for (let j = 0; j < BEATS.length; j++) $("beat" + j).classList.toggle("on", j === i); };
  function beatsFor(e, k) {
    if (k === "join" && e.t < "10:00") on(0);
    if (k === "ask") on(2);
    if (k === "join" && e.t >= "10:00") on(3);
    if (k === "round" && e.text.startsWith("Round 2")) on(2);
    if (k === "receipt") on(4);
  }
  on(1);

  // ------------------------------------------------------------------ load chart
  const H = D.hours.map(hourLab);
  function drawChart() {
    const s = D.series;
    const tr = [
      { x: H, y: s.no_opt, name: "No optimization", line: { color: "#8b98a5", width: 2, dash: "dot" } },
      { x: H, y: s.alone, name: "Each member alone (same 4-9 PM price)", line: { color: "#f0883e", width: 3 } },
    ];
    if (showNetwork) tr.push({ x: H, y: s.network, name: "Commonwatt network", line: { color: "#3fb950", width: 3.5 } });
    tr.push({ x: H, y: s.lmp_usd_mwh, name: "ISO-NE Boston price ($/MWh)", yaxis: "y2",
              line: { color: "#f2cc60", width: 1, dash: "dash" }, opacity: 0.7 });
    const shapes = [
      { type: "rect", xref: "x", yref: "paper", x0: H[W[0]], x1: H[W[W.length - 1] + 1] || H[23], y0: 0, y1: 1,
        fillcolor: "rgba(63,185,80,0.10)", line: { width: 0 } },
      { type: "rect", xref: "x", yref: "paper", x0: H[D.tou_peak[0]], x1: H[D.tou_peak[D.tou_peak.length - 1]], y0: 0,
        y1: 0.04, fillcolor: "rgba(240,136,62,0.5)", line: { width: 0 } },
    ];
    Plotly.react("chart", tr, {
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { color: "#e6edf3", size: 12 },
      margin: { l: 50, r: 60, t: 10, b: 40 }, legend: { orientation: "h", y: 1.12 },
      xaxis: { gridcolor: "#26313d" }, yaxis: { title: "kW (19 members)", gridcolor: "#26313d", rangemode: "tozero" },
      yaxis2: { title: "$/MWh", overlaying: "y", side: "right", showgrid: false }, shapes,
      annotations: [{ x: H[W[0]], y: 1, xref: "x", yref: "paper", text: "grid ask window", showarrow: false,
                      xanchor: "left", yanchor: "top", font: { color: "#3fb950", size: 11 } }],
    }, { displayModeBar: false, responsive: true });
    $("chart-note").textContent = showNetwork ? "" : "press Play: the network curve appears once the commons commits";
  }
  drawChart();
  const pk = S.peak_kw, ph = S.peak_hour;
  const rise = 100 * (pk.alone / pk.no_opt - 1);
  $("kpis").innerHTML = `
    <div class="kpi alone"><div class="v">${fmt(pk.alone)} kW</div><div class="k">peak when everyone optimizes alone
      (${hourLab(ph.alone)}), ${fmt(rise)}% above no optimization</div></div>
    <div class="kpi netw"><div class="v">${fmt(pk.network)} kW</div><div class="k">peak with the network
      (no optimization: ${fmt(pk.no_opt)} kW). Staggered recharge; ${fmt(S.stagger.deferred_to_overnight_kwh)} kWh
      moved to the overnight valley</div></div>
    <div class="kpi netw"><div class="v">−${fmt(S.window_kw_mean.no_opt - S.window_kw_mean.network)} kW</div>
      <div class="k">in the ask window ${D.window_label}; pooled ${fmt(S.pooled_kw, 1)} of ${fmt(S.ask_kw)} kW in
      ${S.rounds} rounds</div></div>
    <div class="kpi"><div class="v">$${fmt(S.paid_usd, 2)}</div><div class="k">paid to ${S.members_paid} members for
      ${fmt(S.delivered_kwh, 1)} kWh; ${S.hp_only_homes_paid} of ${S.hp_only_homes} heat-pump-only homes earned</div></div>`;

  // ------------------------------------------------------------------ member card + privacy
  const sel = $("member");
  ordered.forEach((m) => { const o = document.createElement("option"); o.value = m.id;
    o.textContent = `${m.id} · ${m.kind_label}${m.receipt ? "" : " (not paid)"}`; sel.appendChild(o); });
  sel.value = byId.home_07 ? "home_07" : ordered[0].id;
  function showMember() {
    const m = byId[sel.value], r = m.receipt;
    $("phone").innerHTML = `<div class="app">Commonwatt · ${m.name}</div>
      <div class="big">${r ? "$" + r.payment_usd.toFixed(2) : "—"}</div>
      <div class="msg">${m.phone || (m.steps.length ? "Not part of today's event: " + m.steps[m.steps.length - 1].reason
        : "No request today.")}</div>
      <span class="tag">${m.kind_label}</span> <span class="lab ${m.label}">${m.label}</span>
      ${r ? `<div class="sig">receipt ${r.receipt_id}<br>${r.delivered_kwh} kWh · signed by guard ${r.guard_public_key.slice(0, 16)}…<br>sig ${r.signature.slice(0, 32)}…<br>prev ${r.prev_hash.slice(0, 24)}…</div>` : ""}`;
    const w = W.map((h) => `${hourLab(h)}`).join(", ");
    $("seen").innerHTML = `<tr><th>field</th><th>value</th></tr>
      <tr><td>can_reduce_kw (${w})</td><td>${m.offer_window_kw ?? "—"}</td></tr>
      <tr><td>planned_kw (${w})</td><td>${W.map((h) => m.planned_kw[h]).join(", ")}</td></tr>
      <tr><td>cost_per_kwh</td><td>$${m.cost_per_kwh.toFixed(2)}</td></tr>
      <tr><td>agent card assets</td><td>${m.assets.join(", ")}</td></tr>`;
    const p = m.private;
    $("private").innerHTML = `<tr><th>field</th><th>value</th></tr>
      <tr><td>owner's kW limit</td><td>${p.owner_limit_kw}</td></tr>
      <tr><td>comfort max</td><td>${p.comfort_max_c ? (p.comfort_max_c * 9 / 5 + 32).toFixed(1) + " °F" : "—"}</td></tr>
      <tr><td>battery reserve</td><td>${p.battery_reserve_pct != null ? fmt(p.battery_reserve_pct) + " %" : "—"}</td></tr>
      <tr><td>meter, 4-8 PM (kW)</td><td>${p.load_kw_sample.join(", ")}</td></tr>`;
    $("steps").innerHTML = "<tr><th>round</th><th>asked</th><th>answer</th><th>why</th></tr>" +
      (m.steps.map((s, i) => `<tr><td>${D.rounds.findIndex((r) => r.requests.some((q) => q === s)) + 1 || i + 1}</td>
        <td>${s.asked_kw} kW</td><td>${s.decision}${s.decision === "counter" ? " " + s.kw + " kW" : ""}</td>
        <td>${s.reason}</td></tr>`).join("") || "<tr><td colspan=4>not asked</td></tr>");
  }
  sel.onchange = showMember; showMember();

  // ------------------------------------------------------------------ fairness
  const kinds = Object.keys(D.fairness);
  Plotly.react("fairchart", [{ type: "bar", x: kinds, y: kinds.map((k) => D.fairness[k].usd),
    marker: { color: ["#79c0ff", "#f2cc60", "#7ee787", "#d2a8ff"] }, text: kinds.map((k) => "$" + D.fairness[k].usd.toFixed(2)),
    textposition: "auto" }], { paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: "#e6edf3", size: 12 }, margin: { l: 40, r: 10, t: 10, b: 30 }, yaxis: { title: "$ today", gridcolor: "#26313d" } },
    { displayModeBar: false, responsive: true });
  $("fairtable").innerHTML = "<tr><th>kind</th><th>members</th><th>paid</th><th>kWh</th><th>$</th></tr>" +
    kinds.map((k) => { const f = D.fairness[k]; return `<tr><td>${k}</td><td>${f.members}</td><td>${f.earning_members}</td>
      <td>${f.kwh}</td><td>$${f.usd.toFixed(2)}</td></tr>`; }).join("") +
    `<tr><td colspan=5>Heat-pump-only homes paid: ${S.hp_only_homes_paid} of ${S.hp_only_homes}</td></tr>`;

  // ------------------------------------------------------------------ sources
  $("labels").innerHTML = Object.entries(D.labels).map(([k, v]) => `<p><span class="lab ${k}">${k}</span> ${v}</p>`).join("");
  $("srctable").innerHTML = "<tr><th>member</th><th>label</th><th>source</th></tr>" +
    ordered.map((m) => `<tr><td>${m.id}</td><td><span class="lab ${m.label}">${m.label}</span></td><td>${m.source}</td></tr>`).join("");
})();
