# Final submission — design

## Site map (all static, under `app/`)

| Page | File | Source of truth |
|---|---|---|
| Scenes (3D story) | `app/presentation/commonwatt-story.html` (already in the repo; pre-rendered, no WebGL) | `app/presentation/story-data.js`, `app/presentation/renders/` |
| Network replay | `app/story.html` (exists) | `app/data/demo.js` |
| Trading history | `app/history.html` (new) | `app/data/week.js` (new) |
| Member app | `app/member.html` (new) | `app/data/demo.js` + `app/data/week.js` |
| About | `app/about.html` (new) | static text + inline SVG |

`app/index.html` becomes a landing page: one-line pitch, the hero number (peak −X% on Jun 24), five big
links. Shared nav lives in `app/nav.js` (injects a `<nav>` into every page; highlights the current one).
Reuse `app/story.css` tokens and the vendored fonts; no new CDNs (works offline). Data files are `.js`
(`window.CW_WEEK = {...}`) so pages open from `file://` without fetch/CORS problems.

## R3 — week simulation

- `commonwatt.members.EVENT_DAY` is a module constant used in 7 places. Make the day a parameter:
  `build_neighborhood(day)` and `scenario.run(ask_kw, window, tool_spec, day=EVENT_DAY)`.
- New `src/commonwatt/week.py`, script `commonwatt-week = "commonwatt.week:main"`:
  - days `2025-06-20 … 2025-06-26`; for event days read the window from `dr_events_2025.csv`
    (15:00–18:00 local → use the story's 17–19 window if the model tool expects 2 h; say which in the README);
    ask kW scales with that day's `selection_load_mw` relative to Jun 24 (60 kW on Jun 24).
  - Non-event days: no ask; record zero trades (still show load).
  - Chain receipts across the week (each day's first receipt's `prev_hash` = previous day's last hash) and
    verify the whole chain with the existing trust/signing code.
  - Output `app/data/week.json` + `app/data/week.js`:
    ```json
    { "version": "...", "label": "simulated", "days": [
        { "day": "2025-06-24", "event": true, "ask_kw": 60, "window": [17,19],
          "pooled_kw": 60.0, "delivered_kwh": 120.0, "paid_usd": 113.09, "members_paid": 17, "rounds": 3,
          "peak_kw": {"alone": 398.3, "network": 286.0, "no_opt": 285.3},
          "blocked": [{"member": "home_03", "reason": "EV must reach 80% by 7 AM"}],
          "receipts": [{"receipt_id": "...", "member_id": "...", "delivered_kwh": 0, "payment_usd": 0,
                        "prev_hash": "...", "hash": "...", "sig_ok": true}] } ],
      "members": { "<id>": { "kind": "...", "daily_usd": [..7], "daily_kwh": [..7] } },
      "ledger": { "receipts": 0, "verified": true, "head": "<hash>" } }
    ```
- **Time-box 25 min.** Fallback if the day can't be parameterized in time: run the Jun 24 engine once per
  event day with the ask scaled by `selection_load_mw`, re-sign receipts with the day's date, and state in
  the README and on the page: "other days reuse Jun 24 member states, scaled by system load (simulated)".
- PBT (`tests/test_week.py`, hypothesis): weekly payouts = sum of receipts; chain verifies; any tampered
  receipt breaks verification; no member is paid on a non-event day; pooled ≤ accepted every day.

## R4 — member phone view

- Picker: `home_07` (household, solar + battery), `home_03` (household + EV, blocked), café
  (small business), library (public institution), HouseZero (large building). Map them to the ids in
  `demo.json` (`members[]` has `kind`, `steps`, `assignment`, `receipt`, `private`, `phone`, `planned_kw`,
  `actual_kw`, `battery`).
- Building image: crop of `app/presentation/renders/{home,cafe,library,office}.webp` via CSS
  `object-position`; overlay a small SVG node with an animated in/out line.
- Sections: header (name, type, live status pill) → power now (in/out kW, arrow) → negotiation card
  (latest step: asked / countered / accepted / blocked + reason) → private limits (lock icon, "never
  shared") → today (kWh, $) → this week (7 bars from `week.json`) → "See it in the network" link.

## R1 — About page and architecture diagram

Architecture (left → right, inline SVG, same colors as the site):
`MA data (HouseZero, BPL, ISO-NE load, weather)` → `ML model: LightGBM forecasts + GridCollective optimizer`
→ `EnergyModelTool contract (tools/contract.py)` → `Member agents (19)` ⇄ `Trust guards (private limits,
signed receipts, hash chain)` ⇄ `Commons coordinator` ⇄ `Grid agent (ISO-NE / utility ask)`. Under it: the
7 protocol messages (`protocol/schemas/`) and the ledger. Planned (dashed): `Planner / utility view`.

Copy for the page (edit freely):
- **Problem.** Massachusetts is electrifying heat and cars, and on hot evenings everyone pulls power at once.
  Clean power exists, in rooftop solar, batteries and pre-cooled buildings, but it is scattered across
  homes, shops and public buildings that each optimize alone, which can create a new, later peak.
- **Commonwatt.** An agent network that turns a neighborhood into an energy commons: every building gets
  an agent that knows its owner's private limits; a coordinator negotiates with them when the grid asks;
  trust guards enforce the limits and sign receipts; the grid sees one reliable resource.
- **Why it's credible.** Trained on Massachusetts data (HouseZero, Boston Public Library, ISO-NE load),
  replayed on the real June 24, 2025 ISO-NE peak day, with property-based tests on the trust guarantees.

## Demo video (≤ 3:00) — record from the site, 1080p, voiceover

| Time | Show | Say |
|---|---|---|
| 0:00–0:20 | Landing → About diagram | The problem: on peak evenings clean power is scattered and every building acts alone. |
| 0:20–1:05 | Scenes: office, home (+ EV next door), café, library | Each member has an agent with private limits; it offers flexibility, not data. |
| 1:05–1:45 | Scenes → network (evening), then Network replay | Grid asks 60 kW; coordinator negotiates; a guard blocks the EV request (80% by 7 AM); library joins live; peak flattens; receipts are signed. |
| 1:45–2:15 | Trading history (week, audit chain) | Seven days, every receipt chained and verified; who earned what by member type. |
| 2:15–2:35 | Member app: household, then café | What one owner sees on their phone. |
| 2:35–3:00 | README / `.kiro` folder | Built with Kiro: steering, specs, hooks, property-based tests caught a rounding bug; Claude drafted, Kiro executed. |

## Submission form text (paste)

- **Name:** Commonwatt — an agent network that turns a neighborhood into an energy commons.
- **Track:** Climate Tech, challenge C3.
- **Description (≈120 words):** use the About copy above plus the June 24 numbers from `summary`
  (peak alone vs. together, pooled kW, $ paid, members paid, receipts verified).
- **Links:** GitHub (public), demo (GitHub Pages), video (YouTube/Vimeo), Kiro write-up
  (`KIRO_USAGE.md#write-up`).
