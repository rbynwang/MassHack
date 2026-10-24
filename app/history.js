/* Trading history: reads window.CW_WEEK (app/data/week.js, written by `uv run commonwatt-week`). */
(function () {
  'use strict';
  var W = window.CW_WEEK, $ = function (id) { return document.getElementById(id); };
  if (!W) { $('app').hidden = true; $('missing').hidden = false; return; }
  var fmt = function (x, d) { return Number(x).toLocaleString('en-US', { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 }); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var pill = function (l) { return '<span class="pill ' + l + '">' + l + '</span>'; };
  var dayLab = function (d) { return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }); };
  var hl = function (h) { return ((h + 11) % 12 + 1) + ' ' + (h < 12 ? 'AM' : 'PM'); };
  var KIND_ORDER = ['large_building', 'household', 'small_business', 'public_institution'];
  var css = getComputedStyle(document.documentElement);
  var C = { solar: css.getPropertyValue('--solar').trim(), strain: css.getPropertyValue('--strain').trim(),
            signal: css.getPropertyValue('--signal').trim(), ink3: css.getPropertyValue('--ink-3').trim() };
  var days = W.days, T = W.totals, L = W.ledger;
  var allReceipts = [];
  days.forEach(function (d) { d.receipts.forEach(function (r) { allReceipts.push(r); }); });

  // ---------------------------------------------------------------- header
  var ev = days.filter(function (d) { return d.event; });
  var traded = ev.filter(function (d) { return d.pooled_kw > 0; });
  $('weekSub').innerHTML = days.length + ' days, ' + ev.length + ' grid asks, ' + traded.length + ' with trades. ' + pill('simulated');
  $('weekStats').innerHTML =
    '<div class="stat s3"><div class="num">$' + fmt(T.paid_usd, 2) + '</div><div class="lab">paid this week</div><p>For ' +
    fmt(T.delivered_kwh, 1) + ' kWh delivered on the grid\'s request.</p>' + pill('simulated') + '</div>' +
    '<div class="stat s1"><div class="num">' + L.receipts + '</div><div class="lab">signed receipts</div><p>' + esc(L.message) +
    '. One hash chain across all ' + days.length + ' days.</p>' + pill('simulated') + '</div>' +
    '<div class="stat"><div class="num">' + (ev.length - traded.length) + '</div><div class="lab">asks the members turned down</div><p>' +
    'When the Boston-zone price was below their costs, every agent declined.</p>' + pill('simulated') + '</div>';
  $('weekNotes').textContent = W.notes.join(' ');

  // ---------------------------------------------------------------- charts
  var X = days.map(function (d) { return dayLab(d.day); });
  var font = { family: 'Archivo, Helvetica Neue, Arial, sans-serif', color: '#15181c', size: 12 };
  var base = { paper_bgcolor: '#fff', plot_bgcolor: '#fff', font: font, margin: { l: 50, r: 50, t: 16, b: 44 },
               legend: { orientation: 'h', y: 1.16 }, xaxis: { showgrid: false } };
  Plotly.newPlot('chDelivered', [
    { type: 'bar', x: X, y: days.map(function (d) { return d.delivered_kwh; }), name: 'kWh delivered', marker: { color: C.solar } },
    { type: 'scatter', mode: 'lines+markers', x: X, y: days.map(function (d) { return d.paid_usd; }), name: '$ paid', yaxis: 'y2',
      line: { color: C.signal, width: 2.5 } },
  ], Object.assign({}, base, { yaxis: { title: 'kWh', gridcolor: '#eef0ed', rangemode: 'tozero' },
    yaxis2: { title: '$', overlaying: 'y', side: 'right', showgrid: false, rangemode: 'tozero' } }), { displayModeBar: false, responsive: true });
  Plotly.newPlot('chPeak', [
    { type: 'bar', x: X, y: days.map(function (d) { return d.peak_kw.alone; }), name: 'Each member alone', marker: { color: C.strain } },
    { type: 'bar', x: X, y: days.map(function (d) { return d.peak_kw.network; }), name: 'Commonwatt network (ask days)', marker: { color: C.solar } },
    { type: 'scatter', mode: 'markers', x: X, y: days.map(function (d) { return d.peak_kw.no_opt; }), name: 'No optimization',
      marker: { color: C.ink3, symbol: 'line-ew-open', size: 22, line: { width: 2 } } },
  ], Object.assign({}, base, { barmode: 'group', yaxis: { title: 'peak kW', gridcolor: '#eef0ed', rangemode: 'tozero' } }),
    { displayModeBar: false, responsive: true });
  $('chDelivered').setAttribute('aria-label', 'Energy delivered and payments per day: ' + days.map(function (d) {
    return dayLab(d.day) + ' ' + fmt(d.delivered_kwh, 1) + ' kWh, $' + fmt(d.paid_usd, 2); }).join('; '));
  $('chPeak').setAttribute('aria-label', 'Peak per day, alone vs network: ' + days.map(function (d) {
    return dayLab(d.day) + ' ' + fmt(d.peak_kw.alone) + ' vs ' + (d.peak_kw.network == null ? 'no ask' : fmt(d.peak_kw.network)) + ' kW'; }).join('; '));

  // ---------------------------------------------------------------- one day
  function showDay(i) {
    var d = days[i];
    document.querySelectorAll('#days button').forEach(function (b, k) { b.setAttribute('aria-pressed', k === i ? 'true' : 'false'); });
    if (!d.event) {
      $('daySum').innerHTML = '<div><b>No ask</b><span>The grid did not ask the commons for help.</span></div>' +
        '<div><b>' + fmt(d.peak_kw.alone) + ' kW</b><span>evening peak with members acting alone ' + pill('simulated') + '</span></div>' +
        '<div><b>$0.00</b><span>paid; no receipts</span></div>';
      $('dayEvents').innerHTML = ''; $('dayReplay').textContent = 'Library: ' + (d.library === 'absent' ? 'not yet a member.' : 'member.');
      return;
    }
    $('daySum').innerHTML =
      '<div><b>' + fmt(d.ask_kw, 1) + ' kW</b><span>asked, ' + hl(d.window[0]) + '–' + hl(d.window[d.window.length - 1] + 1) + ' ' + pill('simulated') + '</span></div>' +
      '<div><b>$' + d.price_usd_per_kwh.toFixed(2) + '</b><span>per kWh, ISO-NE Boston-zone price ' + pill('measured') + '</span></div>' +
      '<div><b>' + fmt(d.pooled_kw, 1) + ' kW</b><span>pooled in ' + d.rounds + ' rounds</span></div>' +
      '<div><b>' + fmt(d.delivered_kwh, 1) + ' kWh</b><span>delivered, $' + fmt(d.paid_usd, 2) + ' to ' + d.members_paid + ' members</span></div>' +
      '<div><b>' + fmt(d.peak_kw.alone) + ' → ' + fmt(d.peak_kw.network) + '</b><span>evening peak kW, alone → network</span></div>';
    var items = [];
    d.blocked.forEach(function (b) { items.push('<li class="blocked"><b>' + esc(b.member) + '</b> blocked by its guard: ' + esc(b.reason.replace('trust guard: ', '')) + '</li>'); });
    d.countered.forEach(function (c) { items.push('<li class="counter"><b>' + esc(c.member) + '</b> countered ' + fmt(c.kw, 1) + ' of ' + fmt(c.asked_kw, 1) + ' kW: ' + esc(c.reason) + '</li>'); });
    if (d.declined.length) items.push('<li class="decline"><b>' + d.declined.length + ' declined</b>: ' + esc(d.declined[0].reason) +
      (d.declined.length > 1 ? ' (and ' + (d.declined.length - 1) + ' more)' : '') + '</li>');
    if (d.library === 'joins') items.push('<li><b>library_01</b> joined the commons during the negotiation.</li>');
    $('dayEvents').innerHTML = items.join('');
    $('dayReplay').innerHTML = d.day === '2025-06-24'
      ? '<a href="story.html#replay">Watch this day\'s negotiation, one message at a time →</a>'
      : 'The step-by-step replay is recorded for June 24; this day\'s messages are summarized above. <a href="story.html#replay">Open the June 24 replay →</a>';
  }
  $('days').innerHTML = days.map(function (d, i) {
    return '<button type="button" data-i="' + i + '">' + dayLab(d.day) + '<small>' + (d.event ? (d.pooled_kw > 0 ? '$' + fmt(d.paid_usd, 2) : 'declined') : 'no ask') + '</small></button>';
  }).join('');
  document.querySelectorAll('#days button').forEach(function (b) { b.onclick = function () { showDay(+b.dataset.i); }; });
  showDay(days.findIndex(function (d) { return d.day === '2025-06-24'; }));

  // ---------------------------------------------------------------- earnings table
  var KIND_LABEL = {}; Object.keys(W.members).forEach(function (m) { KIND_LABEL[W.members[m].kind] = W.members[m].kind_label; });
  var sortCol = 'total', sortDir = -1;
  function renderEarn() {
    var head = '<tr><th data-c="id">member</th>' + days.map(function (d, k) { return '<th class="num" data-c="' + k + '">' + dayLab(d.day).replace(/^\w+, /, '') + '</th>'; }).join('') +
      '<th class="num" data-c="total" aria-sort="' + (sortDir < 0 ? 'descending' : 'ascending') + '">week $</th></tr>';
    var rows = [];
    KIND_ORDER.forEach(function (kind) {
      var ids = Object.keys(W.members).filter(function (m) { return W.members[m].kind === kind; });
      if (!ids.length) return;
      var val = function (m) { var e = W.members[m]; return sortCol === 'id' ? m : sortCol === 'total' ? e.daily_usd.reduce(function (a, b) { return a + b; }, 0) : e.daily_usd[+sortCol]; };
      ids.sort(function (a, b) { var x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : 0) * sortDir; });
      var tot = ids.reduce(function (s, m) { return s + W.members[m].daily_usd.reduce(function (a, b) { return a + b; }, 0); }, 0);
      rows.push('<tr class="group"><td colspan="' + (days.length + 1) + '">' + esc(KIND_LABEL[kind]) + '</td><td class="num">$' + fmt(tot, 2) + '</td></tr>');
      ids.forEach(function (m) {
        var e = W.members[m], t = e.daily_usd.reduce(function (a, b) { return a + b; }, 0);
        rows.push('<tr><td class="mono">' + esc(m) + '</td>' + e.daily_usd.map(function (v, k) {
          return '<td class="num">' + (!e.member_days[k] ? '<span title="not a member yet">—</span>' : v ? fmt(v, 2) : '<span style="color:#b0b5ba">0</span>') + '</td>'; }).join('') +
          '<td class="num"><b>' + fmt(t, 2) + '</b></td></tr>');
      });
    });
    $('earn').innerHTML = head + rows.join('');
    document.querySelectorAll('#earn th').forEach(function (th) {
      th.onclick = function () { var c = th.dataset.c; sortDir = sortCol === c ? -sortDir : (c === 'id' ? 1 : -1); sortCol = c; renderEarn(); };
    });
  }
  renderEarn();

  // ---------------------------------------------------------------- audit trail
  $('audit').innerHTML = '<tr><th>day</th><th>receipt</th><th>member</th><th class="num">kWh</th><th class="num">$</th><th>prev hash → hash</th><th>signature</th><th>check</th></tr>' +
    allReceipts.map(function (r, i) {
      return '<tr><td>' + r.day.slice(5) + '</td><td>' + esc(r.receipt_id.replace('r-ask-', '')) + '</td><td>' + esc(r.member_id) + '</td><td class="num">' +
        fmt(r.delivered_kwh, 2) + '</td><td class="num">' + fmt(r.payment_usd, 2) + '</td><td class="hash">' + esc(r.prev_hash.slice(7, 17)) + '… → ' +
        esc(r.hash.slice(7, 17)) + '…</td><td>' + (r.sig_ok ? 'Ed25519 ok' : 'bad') + '</td><td id="chk' + i + '">–</td></tr>';
    }).join('');

  // SHA-256 (pure JS, so it also works where crypto.subtle is unavailable)
  function sha256(str) {
    var K = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,
      0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,
      0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,
      0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,
      0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    var H = [0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    var b = new TextEncoder().encode(str), n = b.length, L = ((n + 9 + 63) >> 6) << 6, m = new Uint8Array(L);
    m.set(b); m[n] = 0x80; var bits = n * 8; for (var i = 0; i < 8; i++) m[L - 1 - i] = (bits / Math.pow(2, 8 * i)) & 0xff;
    var w = new Uint32Array(64), r = function (x, s) { return (x >>> s) | (x << (32 - s)); };
    for (var o = 0; o < L; o += 64) {
      for (var t = 0; t < 16; t++) w[t] = (m[o + 4 * t] << 24) | (m[o + 4 * t + 1] << 16) | (m[o + 4 * t + 2] << 8) | m[o + 4 * t + 3];
      for (t = 16; t < 64; t++) { var s0 = r(w[t - 15], 7) ^ r(w[t - 15], 18) ^ (w[t - 15] >>> 3), s1 = r(w[t - 2], 17) ^ r(w[t - 2], 19) ^ (w[t - 2] >>> 10); w[t] = (w[t - 16] + s0 + w[t - 7] + s1) | 0; }
      var a = H[0], bb = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (t = 0; t < 64; t++) {
        var S1 = r(e, 6) ^ r(e, 11) ^ r(e, 25), ch = (e & f) ^ (~e & g), t1 = (h + S1 + ch + K[t] + w[t]) | 0;
        var S0 = r(a, 2) ^ r(a, 13) ^ r(a, 22), mj = (a & bb) ^ (a & c) ^ (bb & c), t2 = (S0 + mj) | 0;
        h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = bb; bb = a; a = (t1 + t2) | 0;
      }
      H = [H[0] + a, H[1] + bb, H[2] + c, H[3] + d, H[4] + e, H[5] + f, H[6] + g, H[7] + h].map(function (x) { return x | 0; });
    }
    return H.map(function (x) { return ('00000000' + (x >>> 0).toString(16)).slice(-8); }).join('');
  }
  function hex2buf(h) { var a = new Uint8Array(h.length / 2); for (var i = 0; i < a.length; i++) a[i] = parseInt(h.substr(2 * i, 2), 16); return a; }
  async function sigCheck(r) {
    try {
      if (!(window.crypto && crypto.subtle)) return null;
      var key = await crypto.subtle.importKey('raw', hex2buf(r.guard_public_key), { name: 'Ed25519' }, false, ['verify']);
      return await crypto.subtle.verify({ name: 'Ed25519' }, key, hex2buf(r.signature), new TextEncoder().encode(r.signed_bytes));
    } catch (e) { return null; }
  }
  $('bVerify').onclick = async function () {
    var prev = 'sha256:genesis', bad = 0, sigs = 0, sigsUnchecked = 0;
    for (var i = 0; i < allReceipts.length; i++) {
      var r = allReceipts[i], parsed = JSON.parse(r.canonical);
      var hashOk = 'sha256:' + sha256(r.canonical) === r.hash;
      var linkOk = parsed.prev_hash === prev && r.prev_hash === prev;
      var fieldsOk = parsed.payment_usd === r.payment_usd && parsed.delivered_kwh === r.delivered_kwh && parsed.member_id === r.member_id;
      var s = await sigCheck(r);
      if (s === true) sigs++; else if (s === null) sigsUnchecked++;
      var ok = hashOk && linkOk && fieldsOk && s !== false;
      if (!ok) bad++;
      $('chk' + i).innerHTML = ok ? '<span class="ok-cell">✓</span>' : '<span class="bad-cell">✗ ' + (!hashOk ? 'hash' : !linkOk ? 'link' : !fieldsOk ? 'fields' : 'signature') + '</span>';
      prev = r.hash;
    }
    var head = prev === L.head;
    var res = $('verifyRes');
    res.className = 'res ' + (bad || !head ? 'bad' : 'ok');
    res.textContent = (bad || !head)
      ? bad + ' of ' + allReceipts.length + ' receipts failed the check.'
      : 'All ' + allReceipts.length + ' receipts verified in this browser: every hash recomputed, every link to the previous receipt matches, ' +
        (sigs ? sigs + ' Ed25519 signatures checked' : 'Ed25519 signatures were checked in Python (this browser cannot check them)') +
        (sigs && sigsUnchecked ? ', ' + sigsUnchecked + ' not checkable here' : '') + '. Chain head ' + L.head.slice(7, 19) + '….';
  };
})();
