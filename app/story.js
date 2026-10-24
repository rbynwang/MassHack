/* MassWatt story page. Everything on screen is derived from window.MASSWATT (app/data/demo.js,
   written by `uv run commonwatt-demo`). Only the copy is written here. */
(() => {
  'use strict';
  const D = window.MASSWATT;
  const $ = (id) => document.getElementById(id);
  if (!D) { $('app').hidden = true; $('missing').hidden = false; return; }

  const NS = 'http://www.w3.org/2000/svg';
  const RM = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const SHOW_ALL = location.hash === '#all';
  const S = D.summary, A = D.ask, W = A.window, SER = D.series;
  const byId = Object.fromEntries(D.members.map((m) => [m.id, m]));
  const KINDS = ['large_building', 'household', 'small_business', 'public_institution'];
  const KIND_LABEL = { large_building: 'Large buildings', household: 'Households', small_business: 'Small businesses',
                       public_institution: 'Public institutions' };
  const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const KC = { large_building: cssv('--k-large'), household: cssv('--k-household'), small_business: cssv('--k-small'),
               public_institution: cssv('--k-public') };
  const C = { solar: cssv('--solar'), battery: cssv('--battery'), grid: cssv('--grid'), strain: cssv('--strain'),
              signal: cssv('--signal'), ink: cssv('--ink'), ink2: cssv('--ink-2'), ink3: cssv('--ink-3'), hair: cssv('--hair') };

  // ------------------------------------------------------------------ helpers
  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const fmt = (x, d = 0) => Number(x).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  const hl = (hh) => { const h = ((hh % 24) + 24) % 24; return `${(h + 11) % 12 + 1} ${h < 12 ? 'AM' : 'PM'}`; };
  function hrange(a, b) {
    const pa = a % 24 < 12 ? 'AM' : 'PM', pb = b % 24 < 12 ? 'AM' : 'PM';
    const na = (a + 11) % 12 + 1, nb = (b + 11) % 12 + 1;
    return pa === pb ? `${na}–${nb} ${pb}` : `${na} ${pa}–${nb} ${pb}`;
  }
  const clock = (t) => { const [h, m] = t.split(':').map(Number); return `${(h + 11) % 12 + 1}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`; };
  const pill = (label) => `<span class="pill ${label}">${label}</span>`;
  const argmax = (a) => a.reduce((bi, v, i) => (v > a[bi] ? i : bi), 0);
  const winLabel = hrange(W[0], W[W.length - 1] + 1);
  const touLabel = hrange(D.tou_peak[0], D.tou_peak[D.tou_peak.length - 1] + 1);
  const dayLabel = new Date(D.day + 'T12:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  const receiptsCount = (String(S.ledger).match(/(\d+) receipts/) || [])[1] || S.members_paid;

  // ------------------------------------------------------------------ clay drawing (from docs/reference/commonwatt-story.html)
  const COS = Math.cos(Math.PI / 6);
  const P = (b, x, y, z) => [b.ax + (x - y) * COS * b.k, b.ay + (x + y) * 0.5 * b.k - z * b.k];
  const pstr = (a) => a.map((p) => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  function quad(g, b, pts, cls) { return el('polygon', { points: pstr(pts.map((p) => P(b, p[0], p[1], p[2]))), class: cls }, g); }
  function box(g, b, x0, y0, z0, w, d, h, extra) {
    const e = extra ? ' ' + extra : '', x1 = x0 + w, y1 = y0 + d, z1 = z0 + h;
    quad(g, b, [[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]], 'fr' + e);
    quad(g, b, [[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]], 'fl' + e);
    quad(g, b, [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], 'ft' + e);
  }
  const winY = (g, b, y, xa, xb, za, zb, c) => quad(g, b, [[xa, y, za], [xb, y, za], [xb, y, zb], [xa, y, zb]], c || 'win');
  const winX = (g, b, x, ya, yb, za, zb, c) => quad(g, b, [[x, ya, za], [x, yb, za], [x, yb, zb], [x, ya, zb]], c || 'win');
  function ringPts(fn, n) { const a = []; for (let i = 0; i < n; i++) { const t = i / n * Math.PI * 2; a.push(fn(Math.cos(t), Math.sin(t))); } return a; }
  const circTop = (g, b, cx, cy, z, r, c) => el('polygon', { points: pstr(ringPts((co, si) => P(b, cx + r * co, cy + r * si, z), 16)), class: c }, g);
  function shadowQ(g, b, x0, y0, x1, y1, h) { const s = h * 0.45; quad(g, b, [[x0, y0, 0], [x1 + s, y0 - s * 0.1, 0], [x1 + s, y1 + s * 0.3, 0], [x0 + 0.4, y1 + 0.6, 0]], 'gshadow'); }
  function pvFlat(g, b, x0, y0, z, cols, rows, pw, pd, gx, gy) {
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const x = x0 + c * (pw + gx), y = y0 + r * (pd + gy);
      quad(g, b, [[x, y, z + 0.6], [x + pw, y, z + 0.6], [x + pw, y + pd, z + 0.05], [x, y + pd, z + 0.05]], 'pv');
    }
  }
  function drawOffice(g, b, o) {
    const x0 = -7, y0 = -5, x1 = 7, y1 = 5, h = 10;
    shadowQ(g, b, x0, y0, x1, y1, h); box(g, b, x0, y0, 0, 14, 10, h);
    for (let f = 0; f < 3; f++) {
      const za = 1.3 + f * 3, zb = za + 1.8;
      for (let i = 0; i < 5; i++) { const xa = x0 + 1 + i * 2.6; winY(g, b, y1, xa, xa + 1.8, za, zb); }
      for (let i = 0; i < 4; i++) { const ya = y0 + 0.9 + i * 2.3; winX(g, b, x1, ya, ya + 1.6, za, zb); }
    }
    if (o.pv) pvFlat(g, b, -6.2, -4.2, h, 4, 3, 2.4, 2.4, 0.4, 0.5);
    if (o.battery) box(g, b, x1 + 0.6, 0.5, 0, 2.2, 3.4, 2.4, 'eq');
  }
  function drawHouse(g, b, o) {
    const x0 = -5, y0 = -4, x1 = 5, y1 = 4, h = 5.5, rh = 3.2;
    shadowQ(g, b, x0, y0, x1, y1, h + 1.5);
    quad(g, b, [[x1, y0, 0], [x1, y1, 0], [x1, y1, h], [x1, y0, h]], 'fr');
    quad(g, b, [[x0, y1, 0], [x1, y1, 0], [x1, y1, h], [x0, y1, h]], 'fl');
    winY(g, b, y1, -3.7, -2.5, 0, 2.3, 'door');
    winY(g, b, y1, -1.3, 0.5, 1.0, 2.4); winY(g, b, y1, 1.9, 3.6, 1.0, 2.4);
    winY(g, b, y1, -0.8, 0.8, 3.3, 4.6); winX(g, b, x1, -2.8, -1.2, 1.0, 2.4); winX(g, b, x1, 1.2, 2.8, 1.0, 2.4);
    quad(g, b, [[x0, y0 - 0.5, h - 0.3], [x1, y0 - 0.5, h - 0.3], [x1, 0, h + rh], [x0, 0, h + rh]], 'roofA');
    el('polygon', { points: pstr([P(b, x1, y0, h), P(b, x1, y1, h), P(b, x1, 0, h + rh)]), class: 'fr' }, g);
    quad(g, b, [[x0, 0, h + rh], [x1, 0, h + rh], [x1, y1 + 0.5, h - 0.3], [x0, y1 + 0.5, h - 0.3]], 'roofB');
    if (o.pv) {
      const yE = y1 + 0.5, zE = h - 0.3, zR = h + rh;
      const pt = (u, v) => [x0 + u * 10, yE + (0 - yE) * v, zE + (zR - zE) * v + 0.06];
      for (let r = 0; r < 2; r++) for (let c = 0; c < 4; c++) {
        const u0 = 0.08 + c * 0.215, v0 = 0.14 + r * 0.38;
        quad(g, b, [pt(u0, v0), pt(u0 + 0.2, v0), pt(u0 + 0.2, v0 + 0.33), pt(u0, v0 + 0.33)], 'pv');
      }
    }
    if (o.battery) box(g, b, x1, 1.2, 0.6, 0.5, 1.1, 2.2, 'eq');
    if (o.hp) { box(g, b, x1 + 0.8, y0 + 0.9, 0, 1.4, 1.7, 1.2, 'eq'); }
  }
  function drawShop(g, b, o) {
    const x0 = -6, y0 = -4.5, x1 = 6, y1 = 4.5, h = 5;
    shadowQ(g, b, x0, y0, x1, y1, h); box(g, b, x0, y0, 0, 12, 9, h);
    winY(g, b, y1, -5.3, -1.0, 0.4, 3.0, 'glass'); winY(g, b, y1, -0.4, 1.0, 0, 2.6, 'door'); winY(g, b, y1, 1.6, 5.3, 0.4, 3.0, 'glass');
    winX(g, b, x1, 1.2, 3.6, 0.6, 3.0, 'glass');
    quad(g, b, [[x0 + 0.4, y1, 3.65], [x1 - 0.4, y1, 3.65], [x1 - 0.4, y1 + 1.5, 3.05], [x0 + 0.4, y1 + 1.5, 3.05]], 'awning');
    box(g, b, -3, -2.5, h, 3.5, 3, 1.3, 'eq'); circTop(g, b, -1.25, -1, h + 1.3, 0.9, 'fan');
    if (o.pv) pvFlat(g, b, 1, -3.8, h, 2, 3, 2.0, 2.0, 0.3, 0.4);
  }
  function drawCivic(g, b, o, school) {
    const x0 = -9, y0 = -6, x1 = 9, y1 = 6, h = 6;
    shadowQ(g, b, x0, y0, x1, y1, h + 2); box(g, b, x0, y0, 0, 18, 12, h);
    for (let i = 0; i < 7; i++) { const xa = -8.3 + i * 2.4; if (xa > -1.4 && xa < 0.6) continue; winY(g, b, y1, xa, xa + 1.3, 1.0, 5.0); }
    winY(g, b, y1, -0.9, 0.9, 0, 3.0, 'door');
    for (let i = 0; i < 4; i++) { const ya = -5 + i * 2.6; winX(g, b, x1, ya, ya + 1.3, 1.0, 5.0); }
    box(g, b, -9, -6, h, 8, 12, 2.6);
    if (o.pv) pvFlat(g, b, 0.6, -4.6, h, 3, 3, 2.3, 2.6, 0.4, 0.5);
    if (o.battery) box(g, b, x1 + 0.8, -1, 0, 3, 5, 2.4, 'eq');
    if (school) {
      const a = P(b, -6, 4, h + 2.6), t = P(b, -6, 4, h + 7.2);
      el('line', { x1: a[0], y1: a[1], x2: t[0], y2: t[1], stroke: '#9aa1a7', 'stroke-width': Math.max(0.8, b.k * 0.25) }, g);
      el('polygon', { points: pstr([t, P(b, -6, 6.4, h + 6.6), P(b, -6, 4, h + 5.9)]), class: 'fr' }, g);
    }
  }
  const GLYPH = {   // stage scale and vertical offset per kind; big = inside-one-building view
    large_building: { k: 1.75, dy: 10, big: { k: 5.2, ay: 138 } },
    household: { k: 2.0, dy: 10, big: { k: 6.2, ay: 142 } },
    small_business: { k: 1.9, dy: 6, big: { k: 6.0, ay: 128 } },
    public_institution: { k: 1.5, dy: 9, big: { k: 4.6, ay: 128 } },
  };
  function glyph(g, m, ax, ay, k) {
    const a = m.assets || [];
    const o = { pv: a.includes('pv'), battery: a.includes('battery') || a.includes('shared_battery'), hp: a.includes('heat_pump') };
    const b = { ax, ay, k };
    if (m.kind === 'large_building') drawOffice(g, b, o);
    else if (m.kind === 'household') drawHouse(g, b, o);
    else if (m.kind === 'small_business') drawShop(g, b, o);
    else drawCivic(g, b, o, m.id.startsWith('school'));
  }
  function miniGlyph(m, w = 54, h = 46) {
    const svg = el('svg', { viewBox: `0 0 ${w} ${h}`, 'aria-hidden': 'true' });
    const cfg = GLYPH[m.kind];
    glyph(el('g', {}, svg), m, w / 2, h / 2 + cfg.dy * 0.9, cfg.k * 0.95);
    return svg;
  }

  // ------------------------------------------------------------------ 3.0 top bar + 3.1 hero
  $('topChips').innerHTML = `<span class="chip"><b>${esc(D.commons)}</b></span>
    <span class="chip">${dayLabel} · ISO-NE peak day</span><span class="chip">Model tool: ${esc(D.tool)}</span>`;
  $('heroTitle').textContent = `On New England's peak day, ${D.members.length} Cambridge buildings answered the grid as one, ` +
    'without any of them giving up its limits.';
  const allHp = S.hp_only_homes_paid === S.hp_only_homes;
  $('heroStats').innerHTML = `
    <div class="stat s1"><div class="num">${fmt(S.pooled_kw)}<span class="unit">kW</span></div>
      <div class="lab">delivered on request</div>
      <p>Pooled from ${S.members_paid} members in ${S.rounds} rounds, ${winLabel}.</p>${pill('simulated')}</div>
    <div class="stat s2"><div class="num"><span class="from">${fmt(S.peak_kw.alone)}</span><span class="arrow">→</span><span class="to">${fmt(S.peak_kw.network)}</span><span class="unit">kW</span></div>
      <div class="lab">evening peak</div>
      <p>Members acting alone all recharge when the ${touLabel} price ends; the network staggers it.</p>${pill('simulated')}</div>
    <div class="stat s3"><div class="num">$${fmt(S.paid_usd)}</div>
      <div class="lab">to ${S.members_paid} members</div>
      <p>Including ${allHp ? 'all ' + S.hp_only_homes : S.hp_only_homes_paid + ' of ' + S.hp_only_homes} homes that only have a heat pump.</p>${pill('simulated')}</div>`;

  // ------------------------------------------------------------------ 3.2 why this day
  $('whyReason').textContent = A.reason.replace(/(\d{1,2}):00/g, (_, h) => hl(+h)).replace(/-/g, '–');
  function spark(values, color, fmtv, title, unitLabel) {
    const w = 240, h = 46, max = Math.max(...values), min = Math.min(...values), i = argmax(values);
    const x = (k) => ((k + 0.5) / 24) * w, y = (v) => h - 4 - ((v - min) / (max - min || 1)) * (h - 10);
    const pts = values.map((v, k) => `${x(k).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
    const wx0 = (W[0] / 24) * w, wx1 = ((W[W.length - 1] + 1) / 24) * w;
    return `<div class="spark"><div class="t">${title} ${pill('measured')}</div>
      <div class="v">${fmtv(max, i)}</div>
      <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="${title}: ${fmtv(max, i)}">
        <rect x="${wx0}" y="0" width="${wx1 - wx0}" height="${h}" fill="rgba(45,184,98,.13)"/>
        <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/>
        <circle cx="${x(i)}" cy="${y(max)}" r="3" fill="${color}"/></svg>
      <div class="t" style="justify-content:space-between"><span>12 AM</span><span>${unitLabel}</span><span>11 PM</span></div></div>`;
  }
  $('sparks').innerHTML =
    spark(SER.system_load_mw, C.grid, (v, i) => `peak ${fmt(v)} MW at ${hl(i)}`, 'ISO-NE system load', 'shaded: the ask') +
    spark(SER.lmp_usd_mwh, C.battery, (v) => `up to $${fmt(v)}/MWh`, 'Boston-zone real-time price', 'shaded: the ask') +
    spark(SER.temp_out_c, C.strain, (v, i) => `high ${fmt(v, 1)} °C (${fmt(v * 9 / 5 + 32)} °F) at ${hl(i)}`,
          'Outdoor temperature, Cambridge', 'shaded: the ask');

  // ------------------------------------------------------------------ 3.3 alone vs together
  (function mainChart() {
    const X = D.hours.map((h) => h + 0.5);
    const pk = S.peak_kw, ph = S.peak_hour, wm = S.window_kw_mean;
    const ymax = Math.max(...SER.alone, ...SER.network, ...SER.no_opt) * 1.2;
    const font = { family: 'Archivo, Helvetica Neue, Arial, sans-serif', color: C.ink, size: 12.5 };
    const traces = [
      { x: X, y: SER.no_opt, name: 'No optimization', mode: 'lines', line: { color: C.ink3, width: 1.6, dash: 'dot' },
        hovertemplate: 'No optimization %{y:.0f} kW<extra></extra>' },
      { x: X, y: SER.alone, name: 'Each member alone', mode: 'lines', line: { color: C.strain, width: 4 },
        hovertemplate: 'Alone %{y:.0f} kW<extra></extra>' },
      { x: X, y: SER.network, name: 'MassWatt network', mode: 'lines', line: { color: C.solar, width: 4 },
        hovertemplate: 'Network %{y:.0f} kW<extra></extra>' },
    ];
    const wx0 = W[0], wx1 = W[W.length - 1] + 1, mid = (wx0 + wx1) / 2;
    const narrow = window.innerWidth < 640;
    const shapes = [
      { type: 'rect', xref: 'x', yref: 'paper', x0: wx0, x1: wx1, y0: 0, y1: 1, fillcolor: 'rgba(45,184,98,.10)', line: { width: 0 }, layer: 'below' },
      { type: 'rect', xref: 'x', yref: 'paper', x0: D.tou_peak[0], x1: D.tou_peak[D.tou_peak.length - 1] + 1, y0: 0, y1: 0.018,
        fillcolor: 'rgba(221,85,65,.45)', line: { width: 0 } },
      { type: 'line', x0: mid, x1: mid, y0: wm.network, y1: wm.no_opt, line: { color: C.ink, width: 1.5 } },
      { type: 'line', x0: mid - 0.18, x1: mid + 0.18, y0: wm.no_opt, y1: wm.no_opt, line: { color: C.ink, width: 1.5 } },
      { type: 'line', x0: mid - 0.18, x1: mid + 0.18, y0: wm.network, y1: wm.network, line: { color: C.ink, width: 1.5 } },
    ];
    const annotations = [
      { x: ph.alone + 0.5, y: pk.alone, ax: narrow ? -36 : -60, ay: -18,
        text: narrow ? `<b>${fmt(pk.alone)} kW</b> alone` : `<b>${fmt(pk.alone)} kW</b>: everyone recharges when the price drops`,
        showarrow: true, arrowhead: 0, arrowwidth: 1.2, arrowcolor: C.strain, xanchor: 'right', font: { ...font, size: narrow ? 11 : 12.5 } },
      { x: ph.network + 0.5, y: pk.network, ax: narrow ? -30 : -40, ay: narrow ? 70 : 92,
        text: narrow ? `<b>${fmt(pk.network)} kW</b> staggered` : `<b>${fmt(pk.network)} kW</b>: recharge staggered,<br>${fmt(S.stagger.deferred_to_overnight_kwh)} kWh moved overnight`,
        showarrow: true, arrowhead: 0, arrowwidth: 1.2, arrowcolor: C.solar, xanchor: 'center', yanchor: 'top', align: 'center', font: { ...font, size: narrow ? 11 : 12.5 } },
      { x: narrow ? wx0 - 0.15 : wx1 + 0.15, y: narrow ? wm.network - 28 : (wm.network + wm.no_opt) / 2 - 18,
        text: narrow ? `<b>−${fmt(wm.no_opt - wm.network)} kW</b>` : `<b>−${fmt(wm.no_opt - wm.network)} kW</b><br>during the grid's ask`,
        showarrow: false, xanchor: narrow ? 'right' : 'left', align: 'left', font: { ...font, size: narrow ? 11 : 12.5 } },
      { x: mid, y: 1, yref: 'paper', text: narrow ? `Ask, ${winLabel}` : `Grid's ask, ${winLabel}`, showarrow: false, yanchor: 'bottom',
        font: { ...font, size: narrow ? 11 : 12, color: '#1d8a4a' } },
      { x: D.tou_peak[0], y: 0.03, yref: 'paper', text: narrow ? 'time-of-use peak' : `${touLabel} time-of-use peak`, showarrow: false,
        xanchor: 'left', yanchor: 'bottom', font: { ...font, size: narrow ? 10 : 11, color: C.strain } },
    ];
    const ticks = narrow ? [0, 6, 12, 18, 24] : [0, 3, 6, 9, 12, 15, 18, 21, 24];
    Plotly.newPlot('mainChart', traces, {
      paper_bgcolor: '#fff', plot_bgcolor: '#fff', font, showlegend: false, hovermode: 'x unified',
      margin: narrow ? { l: 46, r: 10, t: 24, b: 40 } : { l: 58, r: 24, t: 26, b: 44 },
      xaxis: { range: [0, 24], tickvals: ticks, ticktext: ticks.map((t) => (t === 24 ? '12 AM' : hl(t))), showgrid: false,
               zeroline: false, linecolor: C.hair, ticks: '' },
      yaxis: { range: [0, ymax], title: { text: `kW, all ${D.members.length} members`, standoff: 10 }, gridcolor: '#eef0ed',
               zeroline: false, ticksuffix: '' },
      shapes, annotations,
    }, { displayModeBar: false, responsive: true, staticPlot: false });
    const alt = `Neighborhood load on ${dayLabel}, by hour. Acting alone, the ${D.members.length} members peak at ${fmt(pk.alone)} kW at ${hl(ph.alone)}. ` +
      `With the network, the highest hour is ${fmt(pk.network)} kW at ${hl(ph.network)}, and during ${winLabel} the load averages ` +
      `${fmt(wm.network)} kW instead of ${fmt(wm.no_opt)} kW with no optimization. Simulated.`;
    $('chartAlt').textContent = alt;
    $('mainChart').setAttribute('aria-label', alt);
    $('chartSub').innerHTML = `Neighborhood load, ${dayLabel}. ${pill('simulated')}`;
    $('chartLegend').innerHTML = `<span class="alone">Each member alone, reacting to the same ${touLabel} price</span>
      <span class="net">MassWatt network</span><span class="ref">No optimization</span>
      <span class="win">Grid's ask, ${winLabel}</span><span class="tou">Time-of-use peak, ${touLabel}</span>`;
  })();

  // ------------------------------------------------------------------ 3.4 replay: steps and chapters
  const decisionOf = (e) => {
    if (!e) return 'none';
    const t = e.text;
    return t.startsWith('Accept') ? 'accept' : t.startsWith('Counter') ? 'counter' : t.startsWith('Decline') ? 'decline'
      : t.startsWith('Blocked') ? 'blocked' : 'none';
  };
  const ROUNDQ = D.rounds.map((r) => r.requests.map((q) => ({ ...q, round: r.round, used: false })));
  function buildSteps(log) {
    const steps = []; let i = 0, askSeen = false, round = 0;
    const take = (pred) => { const out = []; while (i < log.length && pred(log[i])) out.push(log[i++]); return out; };
    while (i < log.length) {
      const e = log[i];
      if (e.type === 'agent_card' && !askSeen) {
        const b = take((x) => x.type === 'agent_card');
        steps.push({ kind: 'forms', t: b[0].t, entries: b, members: b.map((x) => x.from) });
      } else if (e.type === 'ask' && e.from === 'grid') {
        askSeen = true; i++; steps.push({ kind: 'gridask', t: e.t, entries: [e], key: true });
      } else if ((e.type === 'ask' && e.from === 'coordinator') || e.type === 'offer') {
        const b = take((x) => (x.type === 'ask' && x.from === 'coordinator') || x.type === 'offer');
        const calls = b.filter((x) => x.type === 'ask'), offers = b.filter((x) => x.type === 'offer');
        if (calls.length > 1) {
          steps.push({ kind: 'fanout', t: calls[0].t, entries: calls, members: calls.map((x) => x.to) });
          steps.push({ kind: 'offers', t: (offers[0] || calls[0]).t, entries: offers, members: offers.map((x) => x.from) });
        } else steps.push({ kind: 'offer1', t: b[0].t, entries: b, members: offers.map((x) => x.from), member: (offers[0] || {}).from });
      } else if (e.type === 'agent_card') {
        i++; steps.push({ kind: 'join', t: e.t, entries: [e], member: e.from, key: true });
      } else if (e.type === 'private') {
        i++; steps.push({ kind: 'private', t: e.t, entries: [e], member: e.from.replace('guard:', ''), key: true });
      } else if (e.type === 'round') {
        i++; round = +((e.text.match(/Round (\d+)/) || [])[1] || round + 1);
        steps.push({ kind: 'round', t: e.t, entries: [e], round });
      } else if (e.type === 'request' && e.from === 'coordinator') {
        const m = e.to.replace('guard:', ''); i++;
        const ent = [e, ...take((x) => x.type === 'request' && x.from === `guard:${m}`)];
        let resp = null;
        if (i < log.length && log[i].type === 'response' && (log[i].from === m || log[i].from === `guard:${m}`)) { resp = log[i++]; ent.push(resp); }
        const dec = decisionOf(resp);
        const q = (ROUNDQ[round - 1] || []).find((x) => x.member === m && !x.used);
        if (q) q.used = true;
        steps.push({ kind: 'exchange', t: e.t, entries: ent, member: m, decision: dec, q, round, key: dec !== 'accept' });
      } else if (e.type === 'response' && e.text.startsWith('Pooled')) {
        i++; steps.push({ kind: 'committed', t: e.t, entries: [e], key: true });
      } else if (e.type === 'assignment') {
        const b = take((x) => x.type === 'assignment'); steps.push({ kind: 'assign', t: b[0].t, entries: b, members: b.map((x) => x.to) });
      } else if (e.type === 'receipt') {
        const b = take((x) => x.type === 'receipt'); steps.push({ kind: 'receipts', t: b[0].t, entries: b, members: b.map((x) => x.to) });
      } else if (e.type === 'ledger') {
        i++; steps.push({ kind: 'ledger', t: e.t, entries: [e], key: true });
      } else { i++; steps.push({ kind: 'other', t: e.t, entries: [e] }); }
    }
    steps.forEach((s, k) => s.entries.forEach((x) => { x._step = k; }));
    return steps;
  }
  const STEPS = buildSteps(D.log);
  const CHAPTERS = [];
  STEPS.forEach((s, k) => {
    let label = null;
    if (s.kind === 'forms') label = 'Network forms';
    else if (s.kind === 'gridask') label = 'Grid asks';
    else if (s.kind === 'fanout') label = 'Offers';
    else if (s.kind === 'round') label = `Round ${s.round}`;
    else if (s.kind === 'join') label = `${(byId[s.member] || { name: s.member }).name.replace(/\s*\d+$/, '')} joins`;
    else if (s.kind === 'committed') label = 'Committed';
    else if (s.kind === 'receipts') label = 'Receipts';
    if (label) CHAPTERS.push({ label, t: s.t, idx: k });
  });
  const chapterOf = (k) => { let c = null; for (const ch of CHAPTERS) if (ch.idx <= k) c = ch; return c; };

  // ------------------------------------------------------------------ 3.4 stage
  const svg = $('stage');
  const POS = { grid: [380, 44], coordinator: [380, 262], registry: [318, 538], ledger: [442, 538] };
  const CL = {
    large_building: { cx: 145, cy: 160, cols: 2, dx: 104, dy: 100 },
    small_business: { cx: 615, cy: 160, cols: 3, dx: 84, dy: 96 },
    household: { cx: 192, cy: 418, cols: 5, dx: 74, dy: 92 },
    public_institution: { cx: 608, cy: 418, cols: 2, dx: 108, dy: 90 },
  };
  const gArcs = el('g', {}, svg), gNodes = el('g', {}, svg), gFx = el('g', {}, svg);
  const NODES = {};
  KINDS.forEach((kind) => {
    const ms = D.members.filter((m) => m.kind === kind), c = CL[kind];
    const rows = Math.ceil(ms.length / c.cols);
    const top = c.cy - ((rows - 1) / 2) * c.dy;
    const t = el('text', { x: c.cx, y: top - 40, class: 'clabel', 'text-anchor': 'middle' }, gNodes);
    t.textContent = KIND_LABEL[kind];
    ms.forEach((m, i) => {
      const row = Math.floor(i / c.cols), inRow = Math.min(c.cols, ms.length - row * c.cols), col = i % c.cols;
      const x = c.cx + (col - (inRow - 1) / 2) * c.dx, y = c.cy + (row - (rows - 1) / 2) * c.dy;
      POS[m.id] = [x, y];
      const g = el('g', { class: 'member hidden', 'data-id': m.id }, gNodes);
      const guard = el('circle', { cx: x, cy: y, r: 32, class: 'guard' }, g);
      const ring = el('circle', { cx: x, cy: y, r: 28, class: 'ring' }, g);
      glyph(el('g', {}, g), m, x, y + GLYPH[kind].dy, GLYPH[kind].k);
      const slash = el('line', { x1: x - 20, y1: y + 20, x2: x + 20, y2: y - 20, class: 'slash', opacity: 0 }, g);
      const badge = el('g', { class: 'badge', opacity: 0 }, g);
      el('rect', { x: x + 13, y: y - 34, width: 20, height: 14, rx: 3.5 }, badge);
      el('text', { x: x + 23, y: y - 24 }, badge).textContent = '$';
      el('text', { x, y: y + 43, class: 'mlabel' }, g).textContent = m.id;
      const title = el('title', {}, g); title.textContent = `${m.id} · ${m.kind_label}`;
      NODES[m.id] = { g, ring, guard, slash, badge };
    });
  });
  (function utilityNodes() {
    const [gx, gy] = POS.grid;
    el('circle', { cx: gx, cy: gy, r: 20, class: 'gridnode' }, gNodes);
    el('path', { d: `M${gx - 6} ${gy + 9} L${gx - 2} ${gy - 10} L${gx + 2} ${gy - 10} L${gx + 6} ${gy + 9} M${gx - 8} ${gy - 4} L${gx + 8} ${gy - 4} M${gx - 5} ${gy + 2} L${gx + 5} ${gy + 2}`,
               fill: 'none', stroke: C.grid, 'stroke-width': 1.6, 'stroke-linecap': 'round' }, gNodes);
    el('text', { x: gx + 30, y: gy - 2, class: 'nlabel', style: 'text-anchor:start' }, gNodes).textContent = 'Grid agent';
    el('text', { x: gx + 30, y: gy + 12, class: 'nsub', style: 'text-anchor:start' }, gNodes).textContent = 'ISO-NE, measured prices';
    const [cx, cy] = POS.coordinator;
    el('circle', { cx, cy, r: 30, class: 'coord' }, gNodes);
    for (let k = 0; k < 6; k++) { const a = k * Math.PI / 3; el('line', { x1: cx, y1: cy, x2: cx + 15 * Math.cos(a), y2: cy + 15 * Math.sin(a), stroke: '#fff', 'stroke-width': 1.6 }, gNodes); }
    el('circle', { cx, cy, r: 5.5, class: 'coordhub' }, gNodes);
    el('text', { x: cx, y: cy + 48, class: 'nlabel' }, gNodes).textContent = 'Coordinator';
    el('text', { x: cx, y: cy + 61, class: 'nsub' }, gNodes).textContent = 'sees offers only';
    [['registry', 'Registry', 'agent cards'], ['ledger', 'Ledger', 'signed receipts']].forEach(([id, a, b2]) => {
      const [x, y] = POS[id];
      el('rect', { x: x - 34, y: y - 14, width: 68, height: 22, rx: 7, class: 'utility' }, gNodes);
      el('text', { x, y: y + 1, class: 'nsub', style: 'fill:#15181c;font-weight:600' }, gNodes).textContent = a;
      el('text', { x, y: y + 21, class: 'nsub' }, gNodes).textContent = b2;
    });
  })();
  $('stateLegend').innerHTML = [['#c4c9c3', 'idle'], [C.signal, 'offered'], [C.solar, 'accepted'], [C.battery, 'countered'],
    ['#a4aaa3', 'declined (slash)'], [C.strain, 'blocked by its guard']].map(([c, t]) => `<span><i style="border-color:${c}"></i>${t}</span>`).join('') +
    `<span><i style="border-color:${C.solar};background:${C.solar};border-radius:3px"></i>paid</span>`;

  const posOf = (id) => POS[String(id).replace(/^guard:/, '')] || POS.coordinator;
  function arcD(a, b) {
    const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1, off = Math.min(46, len * 0.16);
    const cx = (a[0] + b[0]) / 2 - (dy / len) * off, cy = (a[1] + b[1]) / 2 + (dx / len) * off;
    return `M${a[0].toFixed(1)} ${a[1].toFixed(1)} Q${cx.toFixed(1)} ${cy.toFixed(1)} ${b[0].toFixed(1)} ${b[1].toFixed(1)}`;
  }
  let animToken = 0;
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  function travel(path, color, dur, token) {
    return new Promise((resolve) => {
      const len = path.getTotalLength(), dot = el('circle', { r: 5, fill: color, class: 'dot' }, gFx), t0 = performance.now();
      const tick = (now) => {
        if (token !== animToken) { dot.remove(); return resolve(); }
        const f = Math.min(1, (now - t0) / dur), p = path.getPointAtLength(len * f);
        dot.setAttribute('cx', p.x); dot.setAttribute('cy', p.y);
        if (f < 1) requestAnimationFrame(tick); else { dot.remove(); resolve(); }
      };
      requestAnimationFrame(tick);
    });
  }
  function fadeArcs() { [...gArcs.children].forEach((a) => { a.classList.add('fade'); setTimeout(() => a.remove(), 650); }); }
  async function send(from, to, color, dur, token) {
    fadeArcs();
    const path = el('path', { d: arcD(posOf(from), posOf(to)), class: 'arc', stroke: color, opacity: 0.55 }, gArcs);
    await travel(path, color, dur, token);
  }
  function pulse(at, color, dur, token, rmax = 300) {
    return new Promise((resolve) => {
      const [x, y] = posOf(at), c = el('circle', { cx: x, cy: y, r: 10, class: 'pulse', stroke: color }, gFx), t0 = performance.now();
      const tick = (now) => {
        if (token !== animToken) { c.remove(); return resolve(); }
        const f = Math.min(1, (now - t0) / dur);
        c.setAttribute('r', 10 + f * rmax); c.setAttribute('opacity', (1 - f) * 0.8);
        if (f < 1) requestAnimationFrame(tick); else { c.remove(); resolve(); }
      };
      requestAnimationFrame(tick);
    });
  }
  function converge(ids, to, color, dur, token) {
    fadeArcs();
    return Promise.all(ids.map((id, k) => {
      const p = el('path', { d: arcD(posOf(id), posOf(to)), fill: 'none', stroke: 'none' }, gArcs);
      return wait((k * dur) / (ids.length * 3)).then(() => travel(p, color, dur * 0.7, token));
    }));
  }

  // ------------------------------------------------------------------ 3.4 state
  const DEC_STATE = { accept: 'accepted', counter: 'countered', decline: 'declined', blocked: 'blocked' };
  function fresh() { return { visible: new Set(), st: {}, priv: new Set(), paid: new Set(), committed: {}, ticks: [], t: STEPS[0] ? STEPS[0].t : '' }; }
  function apply(st, s) {
    st.t = s.t;
    if (s.kind === 'forms') s.members.forEach((m) => { st.visible.add(m); st.st[m] = 'idle'; });
    if (s.kind === 'offers' || s.kind === 'offer1') s.members.forEach((m) => { st.st[m] = 'offered'; });
    if (s.kind === 'join') { st.visible.add(s.member); st.st[s.member] = 'idle'; }
    if (s.kind === 'private') st.priv.add(s.member);
    if (s.kind === 'round' && s.round > 1 && D.rounds[s.round - 2]) st.ticks.push({ r: s.round - 1, kw: D.rounds[s.round - 2].pooled_kw });
    if (s.kind === 'committed' && D.rounds.length) st.ticks.push({ r: D.rounds.length, kw: D.rounds[D.rounds.length - 1].pooled_kw });
    if (s.kind === 'exchange') {
      st.st[s.member] = DEC_STATE[s.decision] || st.st[s.member];
      if ((s.decision === 'accept' || s.decision === 'counter') && s.q) st.committed[s.member] = s.q.kw;
    }
    if (s.kind === 'receipts') s.members.forEach((m) => st.paid.add(m));
  }
  function stateAt(k) { const st = fresh(); for (let j = 0; j <= k; j++) apply(st, STEPS[j]); if (k < 0) st.t = STEPS[0].t; return st; }

  function renderStage(st, popId) {
    for (const id in NODES) {
      const n = NODES[id], s = st.st[id] || 'idle';
      n.g.classList.toggle('hidden', !st.visible.has(id));
      n.g.classList.toggle('pop', id === popId && !RM);
      n.ring.setAttribute('class', 'ring ' + s);
      n.guard.setAttribute('class', 'guard' + (s === 'blocked' ? ' blocked' : st.priv.has(id) ? ' private' : ''));
      n.slash.setAttribute('opacity', s === 'declined' ? 1 : 0);
      n.badge.setAttribute('opacity', st.paid.has(id) ? 1 : 0);
    }
    // pooled meter
    const byKind = {}; let total = 0;
    for (const m in st.committed) { const k = byId[m].kind; byKind[k] = (byKind[k] || 0) + st.committed[m]; total += st.committed[m]; }
    $('pooledFill').innerHTML = KINDS.map((k) => `<i title="${KIND_LABEL[k]}: ${fmt(byKind[k] || 0, 1)} kW" style="width:${Math.min(100, ((byKind[k] || 0) / A.kw) * 100)}%;background:${KC[k]}"></i>`).join('');
    $('pooledTicks').innerHTML = st.ticks.map((t, i) => {
      const left = Math.min(100, (t.kw / A.kw) * 100), near = left > 50;
      return `<div class="ptick" style="left:${left}%"><span class="${near ? 'end' : ''}" style="top:${28 + i * 13}px">after round ${t.r}: ${fmt(t.kw, 1)} kW</span></div>`;
    }).join('') + '<div class="ptick target" style="left:100%"></div>';
    $('pooledVal').textContent = `${fmt(total, 1)} of ${fmt(A.kw)} kW`;
  }

  // ------------------------------------------------------------------ 3.4 panel text
  const qkw = (s) => (s.q ? s.q : { asked_kw: 0, kw: 0, reason: '' });
  function sentence(s) {
    const q = qkw(s), m = s.member;
    switch (s.kind) {
      case 'forms': return `${s.members.length} buildings register their agent cards: owner, kind and assets. No meter data.`;
      case 'gridask': return `The grid asks the commons to reduce ${fmt(A.kw)} kW from ${winLabel}, paying $${A.price_usd_per_kwh.toFixed(2)}/kWh.`;
      case 'fanout': return `The coordinator asks all ${s.members.length} members what they can offer for ${winLabel}.`;
      case 'offers': return `${s.members.length} offers come back: how much each could reduce, and what it costs. Nothing else.`;
      case 'private': return `${m}'s owner changes a private limit. The coordinator is not told.`;
      case 'round': return s.entries[0].text.replace(', asking', '. Asking').replace(/ 1 members/, ' 1 member') + '.';
      case 'exchange':
        if (s.decision === 'accept') return `Asked ${m} for ${fmt(q.asked_kw, 1)} kW. Accepted.`;
        if (s.decision === 'counter') return `${m} countered: ${fmt(q.kw, 1)} of the ${fmt(q.asked_kw, 1)} kW asked.`;
        if (s.decision === 'decline') return `${m} declined.`;
        if (s.decision === 'blocked') return `${m}'s guard blocked the request.`;
        return `Asked ${m}.`;
      case 'join': return `${m} joins the commons in the middle of the negotiation.`;
      case 'offer1': return `${m} sends its offer, the same message every member sends.`;
      case 'committed': return `${s.entries[0].text.replace('Pooled: ', '')} to the grid by ${S.members_paid} members.`;
      case 'assign': return `Each of the ${s.members.length} members gets its assignment, with a staggered recharge time.`;
      case 'receipts': return `At ${clock(s.t)}, each member's guard measures what it delivered and signs a receipt.`;
      case 'ledger': return `${s.entries[0].text.replace('Ledger check: ', '')}. The chain of signed receipts checks out.`;
      default: return s.entries[0].text;
    }
  }
  function card(s) {
    const q = qkw(s), m = s.member, mem = byId[m];
    const c = (cls, kt, kh, kw) => ({ cls, kt, kh, kw, mem });
    switch (s.kind) {
      case 'gridask': return c('ask', 'Grid asks', `Reduce ${fmt(A.kw)} kW, ${winLabel}`, $('whyReason').textContent);
      case 'private': return c('private', 'Private limit', esc(s.entries[0].text.split(';')[0]),
        `Only ${m}'s guard knows this. The coordinator sees an unchanged offer.`);
      case 'exchange':
        if (s.decision === 'counter') return c('counter', 'Countered', `${m}: ${fmt(q.kw, 1)} of ${fmt(q.asked_kw, 1)} kW`, esc(q.reason));
        if (s.decision === 'decline') return c('decline', 'Declined', `${m} said no`, esc(q.reason));
        if (s.decision === 'blocked') return c('blocked', 'Blocked by its guard', `Request to ${m}: ${fmt(q.asked_kw, 1)} kW`,
          "Over the owner's private limit. The coordinator learns only that it was blocked, not the limit.");
        return null;
      case 'join': return c('join', 'Live join', `${m} joins the commons`,
        'It registered an agent card and sent an offer. No coordinator change.');
      case 'committed': return c('committed', 'Committed', esc(s.entries[0].text), `${S.members_paid} members, ${S.rounds} rounds, ${winLabel}.`);
      case 'ledger': return c('receipts', 'Receipts', `${receiptsCount} signed receipts`,
        `${esc(s.entries[0].text.replace('Ledger check: ', ''))}. $${fmt(S.paid_usd, 2)} paid for ${fmt(S.delivered_kwh, 1)} kWh.`);
      default: return null;
    }
  }
  function renderPanel(k) {
    const s = STEPS[k];
    $('hapClock').textContent = s ? clock(s.t) : clock(STEPS[0].t);
    const ch = s ? chapterOf(k) : null;
    $('hapChapter').textContent = ch ? ch.label : 'Ready';
    $('hapTitle').textContent = s ? sentence(s) : `Press Play to watch ${D.members.length} agents answer the grid.`;
    const cards = [];
    for (let j = 0; j <= k; j++) { if (STEPS[j].key) { const cd = card(STEPS[j]); if (cd) cards.push({ cd, j }); } }
    const box2 = $('hapCards'); box2.innerHTML = '';
    cards.reverse().slice(0, 4).forEach(({ cd, j }, i) => {
      const div = document.createElement('div');
      div.className = `kcard ${cd.cls}${i > 0 || j !== k ? ' old' : ''}`;
      if (cd.mem) div.appendChild(miniGlyph(cd.mem));
      else { const sv = el('svg', { viewBox: '0 0 54 46', 'aria-hidden': 'true' }); el('circle', { cx: 27, cy: 23, r: 13, fill: cd.cls === 'ask' ? '#fff' : C.signal, stroke: cd.cls === 'ask' ? C.grid : '#fff', 'stroke-width': 2.5 }, sv); div.appendChild(sv); }
      div.insertAdjacentHTML('beforeend', `<div class="kt">${cd.kt}</div><div class="kh">${cd.kh}</div><div class="kw">${cd.kw}</div>`);
      box2.appendChild(div);
    });
    document.querySelectorAll('.chap').forEach((b) => b.classList.toggle('on', ch && +b.dataset.idx === ch.idx));
    $('scrub').value = Math.max(0, k);
  }

  // ------------------------------------------------------------------ 3.4 animation per step
  async function animate(s, token, speed) {
    const d = (ms) => ms / speed;
    switch (s.kind) {
      case 'forms': await converge(s.members, 'registry', C.signal, d(1100), token); break;
      case 'gridask': await send('grid', 'coordinator', C.grid, d(900), token); break;
      case 'fanout': await pulse('coordinator', C.signal, d(1000), token); break;
      case 'offers': await converge(s.members, 'coordinator', C.signal, d(1100), token); break;
      case 'private': await pulse(s.member, '#8a9097', d(800), token, 30); break;
      case 'round': await pulse('coordinator', C.ink3, d(500), token, 60); break;
      case 'exchange': {
        await send('coordinator', s.decision === 'blocked' ? s.member : s.member, C.signal, d(460), token);
        const col = { accept: C.solar, counter: C.battery, decline: '#a4aaa3', blocked: C.strain }[s.decision] || C.ink3;
        await send(s.member, 'coordinator', col, d(460), token); break;
      }
      case 'join': await converge([s.member], 'registry', C.signal, d(800), token); break;
      case 'offer1': await send('coordinator', s.member, C.signal, d(450), token); await send(s.member, 'coordinator', C.signal, d(450), token); break;
      case 'committed': await send('coordinator', 'grid', C.solar, d(900), token); break;
      case 'assign': await pulse('coordinator', C.solar, d(1000), token); break;
      case 'receipts': await converge(s.members, 'ledger', '#1d8a4a', d(1300), token); break;
      case 'ledger': await pulse('ledger', '#1d8a4a', d(700), token, 40); break;
      default: break;
    }
  }
  const BASE = { forms: 1300, gridask: 1100, fanout: 1100, offers: 1300, private: 900, round: 900, exchange: 1000, join: 1000,
                 offer1: 950, committed: 1100, assign: 1100, receipts: 1500, ledger: 900, other: 500 };

  // ------------------------------------------------------------------ 3.4 player
  let cur = -1, playing = false, timer = null;
  const speed = () => +$('speed').value || 1;
  function show(k, anim) {
    animToken++;
    cur = Math.max(-1, Math.min(STEPS.length - 1, k));
    const st = stateAt(cur);
    const s = STEPS[cur];
    renderStage(st, s && s.kind === 'join' ? s.member : null);
    renderPanel(cur);
    if (anim && s && !RM) animate(s, animToken, speed());
    else { [...gArcs.children].forEach((a) => a.remove()); }
  }
  function schedule() {
    clearTimeout(timer);
    if (!playing) return;
    if (cur >= STEPS.length - 1) { setPlaying(false); return; }
    show(cur + 1, true);
    const s = STEPS[cur];
    const delay = (BASE[s.kind] || 800) / speed() + (s.key ? 2000 / speed() : 0);
    timer = setTimeout(schedule, delay);
  }
  function setPlaying(p) {
    playing = p; $('bPlay').textContent = p ? 'Pause' : (cur >= STEPS.length - 1 ? 'Replay' : 'Play');
    if (p) { if (cur >= STEPS.length - 1) show(-1, false); schedule(); } else clearTimeout(timer);
  }
  $('bPlay').onclick = () => setPlaying(!playing);
  $('bNext').onclick = () => { setPlaying(false); show(cur + 1, true); };
  $('bPrev').onclick = () => { setPlaying(false); show(cur - 1, false); };
  $('bEnd').onclick = () => { setPlaying(false); show(STEPS.length - 1, false); $('bPlay').textContent = 'Replay'; };
  $('speed').onchange = () => { if (playing) schedule(); };
  const scrub = $('scrub'); scrub.max = STEPS.length - 1;
  scrub.oninput = () => { setPlaying(false); show(+scrub.value, false); };
  // chapter markers: true positions as ticks on the track, readable labels as an evenly spaced row of buttons
  $('chapTicks').innerHTML = CHAPTERS.map((c) => `<i style="left:${(c.idx / (STEPS.length - 1)) * 100}%"></i>`).join('');
  $('chapters').innerHTML = CHAPTERS.map((c) => `<button type="button" class="chap" data-idx="${c.idx}">${esc(c.label)}<span class="ct">${clock(c.t)}</span></button>`).join('');
  document.querySelectorAll('.chap').forEach((b) => { b.onclick = () => { setPlaying(false); show(+b.dataset.idx, true); }; });
  document.addEventListener('keydown', (e) => {
    if (e.target.closest && e.target.closest('input, select, textarea, summary')) return;
    if (e.target.tagName === 'BUTTON' && (e.key === ' ' || e.key === 'Enter')) return;
    const r = $('replay').getBoundingClientRect();
    if (r.bottom < 0 || r.top > innerHeight) return;
    if (e.key === ' ') { e.preventDefault(); setPlaying(!playing); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); setPlaying(false); show(cur + 1, true); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); setPlaying(false); show(cur - 1, false); }
  });

  // ------------------------------------------------------------------ 3.4 full log
  const KEY_TYPES = new Set(['private', 'round', 'counter', 'decline', 'blocked', 'pooled', 'ledger', 'join', 'gridask']);
  function rowKind(e) {
    if (e.type === 'response') { const d = decisionOf(e); return d !== 'none' ? d : e.text.startsWith('Pooled') ? 'pooled' : 'response'; }
    if (e.type === 'ask') return e.from === 'grid' ? 'gridask' : 'ask';
    if (e.type === 'agent_card') return STEPS[e._step] && STEPS[e._step].kind === 'join' ? 'join' : 'card';
    return e.type;
  }
  function renderLog() {
    const keyOnly = $('keyOnly').checked;
    const groups = new Map();
    D.log.forEach((e) => {
      const kind = rowKind(e);
      if (keyOnly && !KEY_TYPES.has(kind)) return;
      const ch = chapterOf(e._step); const label = ch ? `${ch.label} · ${clock(ch.t)}` : 'Start';
      if (!groups.has(label)) groups.set(label, []);
      const cls = kind === 'gridask' ? 'ask' : kind;
      groups.get(label).push(`<div class="lrow"><span>${e.t}</span><span class="ty ${cls}">${kind === 'gridask' ? 'ask' : kind}</span>
        <span class="tx"><b>${esc(e.from)}${e.to ? ' → ' + esc(e.to) : ''}</b> ${esc(e.text)}</span><span class="sg">${e.sig ? 'sig ' + esc(e.sig) : ''}</span></div>`);
    });
    $('logGroups').innerHTML = [...groups].map(([g, rows]) => `<div class="lgroup"><h4>${g}</h4>${rows.join('')}</div>`).join('');
  }
  $('logSummary').textContent = `Show all ${D.log.length} signed messages`;
  $('keyOnly').onchange = renderLog;
  renderLog();

  // ------------------------------------------------------------------ 3.5 inside one building
  const roundsFor = (id) => { const out = []; D.rounds.forEach((r) => r.requests.forEach((q) => { if (q.member === id) out.push({ ...q, round: r.round }); })); return out; };
  const F = (c) => (c * 9) / 5 + 32;
  function renderMember(id) {
    const m = byId[id];
    document.querySelectorAll('.pchip').forEach((b) => b.setAttribute('aria-pressed', b.dataset.id === id ? 'true' : 'false'));
    const big = $('bigGlyph'); big.innerHTML = '';
    const cfg = GLYPH[m.kind].big;
    glyph(el('g', {}, big), m, 130, cfg.ay, cfg.k);
    big.setAttribute('aria-label', `${m.name}, ${m.kind_label}: ${(m.assets || []).join(', ')}`);
    $('insideName').innerHTML = `${esc(m.name)} ${pill(m.label)}`;
    const wh = W.map((h) => hl(h));
    $('leaves').innerHTML = `
      <div><dt>can_reduce_kw (${winLabel})</dt><dd>${m.offer_window_kw != null ? fmt(m.offer_window_kw, 2) + ' kW' : '—'}</dd></div>
      <div><dt>planned_kw at ${wh.join(', ')}</dt><dd>${W.map((h) => fmt(m.planned_kw[h], 1)).join(', ')} kW</dd></div>
      <div><dt>cost_per_kwh</dt><dd>$${fmt(m.cost_per_kwh, 2)}</dd></div>
      <div><dt>assets (agent card)</dt><dd>${esc((m.assets || []).join(', ').replace(/_/g, ' '))}</dd></div>`;
    const p = m.private;
    const mf = (D.model_forecasts || {})[id];
    const fcRow = mf ? `<div><dt>trained model's forecast error today</dt><dd>${fmt(mf.day_error_pct, 1)} %</dd></div>`
      : `<div><dt>forecast</dt><dd>stand-in</dd></div>`;
    $('stays').innerHTML = fcRow + `
      <div><dt>owner's kW limit</dt><dd>${fmt(p.owner_limit_kw, 1)} kW</dd></div>
      <div><dt>comfort max</dt><dd>${p.comfort_max_c != null ? fmt(F(p.comfort_max_c), 1) + ' °F' : '—'}</dd></div>
      <div><dt>battery reserve</dt><dd>${p.battery_reserve_pct != null ? fmt(p.battery_reserve_pct) + ' %' : '—'}</dd></div>
      <div><dt>meter, ${hl(16)}–${hl(19)}</dt><dd>${p.load_kw_sample.map((v) => fmt(v, 1)).join(', ')} kW</dd></div>`;
    const steps = roundsFor(id);
    $('memberSteps').innerHTML = steps.length ? steps.map((s) => `<li class="${s.decision}"><div class="r">Round ${s.round}</div>
        <div class="a">Asked ${fmt(s.asked_kw, 1)} kW → ${s.decision === 'counter' ? 'countered ' + fmt(s.kw, 1) + ' kW' : s.decision === 'blocked' ? 'blocked by its guard' : s.decision + (s.decision === 'accept' ? 'ed' : 'd')}</div>
        <div class="w">${esc(s.reason)}</div></li>`).join('') : '<li>Not asked today.</li>';
    const r = m.receipt;
    const facts = [];
    if (r && r.indoor_f_range) facts.push(`indoor ${fmt(r.indoor_f_range[0])}–${fmt(r.indoor_f_range[1])} °F`);
    if (r && r.battery_min_pct != null) facts.push(`battery ≥ ${fmt(r.battery_min_pct)} %`);
    if (r) facts.push(`${fmt(r.delivered_kwh, 1)} kWh`);
    const last = steps[steps.length - 1];
    $('phone').innerHTML = `<div class="app">MassWatt · ${esc(m.name)}</div>
      <div class="pay">${r ? '$' + fmt(r.payment_usd, 2) : '$0.00'}</div>
      <div class="msg">${esc(m.phone || (last ? `Not part of today's event. ${last.decision === 'blocked' ? 'Your guard blocked a request over your limit.' : last.reason}` : 'No request today.'))}</div>
      <div class="facts">${facts.map((f) => `<span>${f}</span>`).join('')}</div>
      ${r ? `<div class="rc">receipt ${esc(r.receipt_id)}<br>sig ${esc(r.signature.slice(0, 24))}…<br>prev ${esc(r.prev_hash.slice(0, 26))}…</div>
      <div class="ver"><svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7.5" fill="#1d8a4a"/><path d="M4.5 8.2l2.3 2.3 4.7-4.9" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>Verified · ${receiptsCount} receipts in the ledger</div>` : ''}`;
  }
  (function picker() {
    const tagOf = (id) => { const st = roundsFor(id).map((s) => s.decision); return st.includes('blocked') ? 'blocked' : st.includes('counter') ? 'countered' : ''; };
    $('picker').innerHTML = KINDS.map((k) => `<div class="pgroup"><span class="pk">${KIND_LABEL[k]}</span>${D.members.filter((m) => m.kind === k)
      .map((m) => { const t = tagOf(m.id); return `<button type="button" class="pchip" data-id="${m.id}" aria-pressed="false">${m.id}${t ? `<span class="tag ${t}">${t}</span>` : ''}</button>`; }).join('')}</div>`).join('');
    document.querySelectorAll('.pchip').forEach((b) => { b.onclick = () => renderMember(b.dataset.id); });
    const hpPaid = D.members.find((m) => m.id === 'home_07') || D.members.find((m) => m.kind === 'household' && !m.battery && m.receipt) || D.members[0];
    renderMember(hpPaid.id);
  })();

  // ------------------------------------------------------------------ 3.6 fairness
  (function fairness() {
    const rows = KINDS.map((k) => ({ k, f: D.fairness[KIND_LABEL[k]] })).filter((r) => r.f).sort((a, b) => b.f.usd - a.f.usd);
    const max = Math.max(...rows.map((r) => r.f.usd), 1);
    $('fairBars').innerHTML = rows.map(({ k, f }) => `<div class="fbar"><div class="fk">${KIND_LABEL[k]}</div>
      <div class="ftrack"><div class="ffill" style="width:${(f.usd / max) * 100}%;background:${KC[k]}"></div></div>
      <div class="fval"><b>$${fmt(f.usd, 2)}</b> · ${f.earning_members} of ${f.members} paid · ${fmt(f.kwh, 1)} kWh</div></div>`).join('') +
      `<div>${pill('simulated')}</div>`;
    $('fairCallout').textContent = `${S.hp_only_homes_paid} of ${S.hp_only_homes} heat-pump-only homes earned.`;
    const top = rows[0];
    const shared = D.members.find((m) => m.kind === top.k && m.battery && m.battery.label === 'assumption');
    $('fairNote').innerHTML = shared
      ? `${KIND_LABEL[top.k]} lead because ${esc(shared.id)}'s ${fmt(shared.battery.kwh)} kWh shared battery is an ${pill('assumption')}, not in the data.`
      : `${KIND_LABEL[top.k]} earned the most in this simulation.`;
  })();

  // ------------------------------------------------------------------ 3.7 methods
  $('labelLegend').innerHTML = Object.entries(D.labels).map(([k, v]) => `<div>${pill(k)} ${esc(v)}</div>`).join('');
  const MD = S.model || {};
  $('toolLine').innerHTML = `Model tool used for these numbers: <b>${esc(D.tool)}</b>. ` +
    (MD.trained_members ? `The trained model forecast and priced decisions for ${MD.trained_members.length} members ` +
      `(${MD.trained_members.map(esc).join(', ')}; mean day error ${fmt(MD.forecast_day_error_pct, 1)} %); ` +
      `${MD.stand_in_members.length} members it was not trained on use the labeled stand-in. ${MD.tool_calls} tool calls this run. ` : '') +
    `Choose a tool with <code>COMMONWATT_TOOL=module:Class</code>.`;
  $('srcTable').innerHTML = '<tr><th>member</th><th>kind</th><th>label</th><th>source</th></tr>' +
    D.members.map((m) => `<tr><td class="mono">${m.id}</td><td>${esc(m.kind_label)}</td><td>${pill(m.label)}</td><td>${esc(m.source)}</td></tr>`).join('');

  // ------------------------------------------------------------------ start
  if (SHOW_ALL) { show(STEPS.length - 1, false); $('bPlay').textContent = 'Replay'; }
  else show(-1, false);
})();
