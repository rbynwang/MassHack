# Commonwatt Demo Page: Redesign Brief

Implementation handoff. Rebuild the demo page (`app/`) so it tells the Commonwatt story in order and shows the project's real results clearly. The data, the agents, and `data/demo.js` stay as they are; this is a front-end redesign only.

**Deadline:** submissions open at 6 PM and close at **8 PM ET today (Oct 24)**. Timebox this to about 75 minutes and ship in the priority order in section 7.

---

## 1. What's Wrong with the Current Page

The data is strong (a real ISO-NE peak day, 19 members, 3 negotiation rounds, signed receipts), but the page hides it:

1. **No story order.** Eight panels with equal weight. A judge has to hunt for the result.
2. **The headline result is buried** in four small KPI boxes under a busy chart.
3. **The network graph is a hairball.** Every message line stays on screen, so the key moments (a counter-offer, a private limit, a blocked request, a decline, a live join) are invisible.
4. **The load chart is overloaded.** A price line on a second axis plus three curves that overlap most of the day; the 9 PM rebound spike, which is the whole point, isn't called out.
5. **Privacy, the main differentiator, is two raw tables** near the bottom.
6. **Sources take as much space as results.**
7. **The style** is a generic dark developer dashboard, unrelated to the presentation video. It should match the presentation's light clay-model look (see `docs/reference/commonwatt-story.html`).

---

## 2. The Data (`window.COMMONWATT`, written by `uv run commonwatt-demo`)

Use these fields; never hardcode the numbers.

| Field | What it holds (current values) |
|---|---|
| `day`, `commons`, `tool` | `2025-06-24` (ISO-NE peak day), `cambridge-commons-01`, `mock (perfect-foresight twin + rules)` |
| `ask` | Reduce **60 kW**, window `[17, 18]` (5–7 PM), **$0.942/kWh**, `reason` (system load peaked at 25,882 MW at 6 PM; Boston price $755–1,129/MWh) |
| `series` | 24 hourly values each: `no_opt`, `alone`, `network`, `lmp_usd_mwh`, `system_load_mw`, `temp_out_c` |
| `tou_peak` | `[16..20]`: the 4–9 PM time-of-use peak every member reacts to when acting alone |
| `summary.peak_kw` | Alone **398.3 kW** at 9 PM, no optimization 285.3, network **286.4** (alone is 40% above no optimization) |
| `summary.window_kw_mean` | In the ask window: no optimization 276.0 → network **210.6** (−65.4 kW) |
| `summary` (other) | Pooled 60.02 of 60 kW in **3 rounds**; 120 kWh delivered; **$113.09 paid to 17 members**; **5 of 5 heat-pump-only homes paid**; `ledger`: "17 receipts verified"; `stagger.deferred_to_overnight_kwh`: 73 |
| `members[]` (19) | `id`, `name`, `kind` (`large_building`, `small_business`, `household`, `public_institution`), `kind_label`, `label` (measured / simulated / assumption), `source`, `assets`, `late_joiner`, `battery`, `cost_per_kwh`, `offer_window_kw`, `steps[]` (asked, decision, kw, reason), `committed_kw`, `assignment`, `receipt` (payment, kWh, indoor °F range, battery min %, guard key, signature, prev hash), `phone` (plain-language summary), `planned_kw[24]`, `actual_kw[24]`, `private` (owner limit, comfort max °C, battery reserve, meter sample) |
| `rounds[]` | R1: need 60, asked 2 (school_01 **counters** 37.5 of 54.3; home_04 accepts) → 43.2. R2: need 16.8, asked 18 (restaurant_01 **declines**, price below its $1.50 cost; home_03 **blocked** by its guard) → 59.8. R3: need 0.2, office_01 → **60.0** |
| `log[]` (160) | `t`, `from`, `to`, `type` (`agent_card`, `ask`, `offer`, `private`, `round`, `request`, `response`, `assignment`, `receipt`, `ledger`), `text`, `msg_id`, `sig` |
| `fairness` | By kind: members, earning members, $, kWh. Public institutions $71.33 (mostly the school's battery, an assumption), households $24.25, large buildings $16.45, small businesses $1.06 |
| `labels` | One-line explanation of measured / simulated / assumption |

**Key moments to find in the log** (detect by type and text prefix, not by index):

| Moment | How to detect | Example |
|---|---|---|
| Network forms | `agent_card` before the `ask` | 18 members register at 09:55 |
| Grid asks | `type === "ask"` from `grid` | 10:00 |
| Private limit change | `type === "private"` | home_03's owner lowers its limit to 0 kW ("guests coming over"); the coordinator never sees it |
| Round start | `type === "round"` | "Round 1: 60.0 kW still needed, asking 2 members" |
| Counter | `response` starting "Counter" | school_01: 37.5 kW for the full 2 h |
| Live join | `agent_card` after the `ask` | library_01 joins at 10:04, "no coordinator change" |
| Decline | `response` starting "Decline" | restaurant_01: price below cost |
| Blocked | `response` starting "Blocked" | guard:home_03 stops a request over the owner's limit |
| Committed | `response` starting "Pooled" | "Pooled: 60.0 kW committed" |
| Receipts | `receipt` at 19:05 | 17 signed receipts, then `ledger` "17 receipts verified" |

---

## 3. Page Structure (in story order)

One scrolling page. Each section has one job.

### 3.0 Top bar
- Wordmark "Commonwatt" (no emoji), plus chips for `commons`, the date ("June 24, 2025 · ISO-NE peak day"), and the model tool. A link "Watch the 1-minute story" to the presentation.

### 3.1 Hero: the result in one sentence and three numbers
- Sentence: "On New England's peak day, 19 Cambridge buildings answered the grid as one, without any of them giving up its limits."
- Three numbers, large, each with a one-line explanation and a `simulated` label pill:
  1. **60 kW delivered on request.** "Pooled from 17 members in 3 rounds, 5–7 PM." (`summary.pooled_kw`, `rounds`)
  2. **398 → 286 kW evening peak.** "Members acting alone all recharge when the 4–9 PM price ends; the network staggers it." (`summary.peak_kw.alone` → `.network`)
  3. **$113 to 17 members.** "Including all 5 homes that only have a heat pump." (`summary.paid_usd`, `hp_only_homes_paid`)

### 3.2 Why this day (context strip)
- A thin strip, not a full chart: small sparklines for ISO-NE system load (peak 25,882 MW at 6 PM), the Boston-zone price (to $1,129/MWh), and outdoor temperature from `series`, with the ask window shaded. One line of copy from `ask.reason`.
- This moves the price line **off** the main chart.

### 3.3 Alone vs. together (the main chart)
- Plot only:
  - `alone`: strain red/orange, thick
  - `network`: green, thick
  - `no_opt`: thin gray dotted reference
- Shade the ask window (5–7 PM). Show the 4–9 PM time-of-use peak as a thin band along the x-axis.
- Two annotations with leader lines:
  - at 9 PM on `alone`: "398 kW: everyone recharges when the price drops"
  - on `network`: "286 kW: recharge staggered, 73 kWh moved overnight"
- A bracket in the window: "−65 kW during the grid's ask".
- Keep Plotly (already vendored, works offline) or draw it in SVG. Either way, restyle to the light theme: no gridline clutter, labeled axes in kW, hours as "5 PM".

### 3.4 Watch the negotiation (the replay)
**Layout:** network stage on the left (about 60%), a "what's happening" panel on the right, and a timeline across the bottom.

**Network stage**
- Coordinator in the center; grid agent above it.
- Members in **four labeled clusters by kind** (large buildings, households, small businesses, public institutions), each member drawn as a small isometric clay glyph for its kind (office block, house, shop, library or school). Reuse the drawing helpers (`P`, `box`, `quad`) from `docs/reference/commonwatt-story.html`.
- Registry and ledger as small utility nodes at the bottom edge.
- **Show only the current message:** one arc with a dot traveling along it. Earlier messages fade out.
- Members keep a persistent state ring:
  - grey: idle
  - indigo: offered
  - green: accepted
  - amber: countered
  - grey with a slash: declined
  - red guard ring: blocked
  - small receipt badge: paid
- Batch the 40 asks and offers visually: one fan-out pulse from the coordinator, then offers returning, instead of 40 separate lines.
- library_01 starts hidden and pops in at its join.

**"What's happening" panel**
- One plain-language sentence per step, e.g. "Round 2: 16.8 kW still needed. Asking 18 members."
- For each key moment, a **callout card** with the member glyph, what happened, and why (use `steps[].reason` and `log.text`). The private-limit card should say explicitly: "Only home_03's guard knows this. The coordinator sees an unchanged offer."

**Pooled meter**
- A horizontal bar from 0 to 60 kW that fills as members commit, in segments colored by member kind, with tick marks where each round ended (43.2, 59.8, 60.0).

**Timeline**
- A scrubber with chapter markers: Network forms (09:55), Grid asks (10:00), Offers (10:01), Round 1 (10:03), Library joins (10:04), Round 2 (10:05), Round 3 (10:06), Committed (10:07), Receipts (7:05 PM).
- Controls: play/pause, step, speed. Space and arrow keys. Clicking a chapter jumps there.

**Full log**
- Collapsed under "Show all 160 signed messages", grouped by chapter, with a type chip and the short `sig` per row. A "Key moments only" filter on by default.

### 3.5 Inside one building (privacy)
- Member picker: chips grouped by kind. Default to **home_07** (a heat-pump-only home that got paid). Also make home_03 (blocked) and school_01 (counter) easy to find.
- Center: the member's glyph. **Left, "Leaves the building":** the offer fields (`offer_window_kw` as can_reduce, `planned_kw` for the window hours, `cost_per_kwh`, `assets`), with an arrow out toward the coordinator. **Right, "Stays inside":** a lock icon and the private fields (owner's kW limit, comfort max converted to °F, battery reserve %, meter sample 4–8 PM).
- Below: this member's negotiation steps as a short horizontal timeline (asked → answer → why).
- A phone-style card: the payment, the `phone` sentence, the indoor °F range, the battery minimum, and the receipt id, signature, and previous hash truncated, with a "Verified · 17 receipts in the ledger" check.

### 3.6 Fairness
- Horizontal bars by kind: dollars earned, with "earning members / members" next to each (e.g. "Households: 9 of 10 paid, $24.25").
- Callout: "5 of 5 heat-pump-only homes earned."
- One honest note: public institutions lead because the school's 100 kWh shared battery is an assumption.

### 3.7 Methods and sources (appendix, collapsed)
- The measured / simulated / assumption legend from `labels`.
- The per-member source table (`member.source`), the model tool name, how to run it (`uv run commonwatt-demo`), and the protocol schemas in `protocol/schemas/`.
- The existing footer text with DOIs and licenses.

---

## 4. Visual System (match the presentation)

| Token | Value | Use |
|---|---|---|
| `--page` | `#e8ebe7` | page background (cool off-white) |
| `--card` | `#ffffff` | section surfaces |
| `--ink` / `--ink-2` / `--ink-3` | `#15181c` / `#565d65` / `#8a9097` | text levels |
| `--hair` | `#dde1dc` | dividers |
| `--solar` | `#2db862` | network curve, accept, clean energy |
| `--battery` | `#e09a2c` | counter, batteries |
| `--grid` | `#2a9a95` | grid power |
| `--strain` | `#dd5541` | alone curve, blocked, decline |
| `--signal` | `#5960f0` | agent messages, request, offered |

- **Label pills:** measured (green tint), simulated (indigo tint), assumption (amber tint). Every number keeps its label.
- **Kind colors** for clusters, the pooled-meter segments, and fairness bars: pick four muted tints that stay distinct from the state colors above. Don't reuse green or red for kinds.
- **Type:** Archivo for display and UI (headings with `font-stretch: 112%`), JetBrains Mono for numbers, ids, and the log. The page must work offline (Plotly is vendored), so **vendor the two fonts** as woff2 in `app/vendor/fonts/` or fall back cleanly to system fonts.
- **Look:**
  - white cards with soft shadows, generous spacing, no heavy borders
  - clay-model glyphs (white, light grey, mid grey faces)
  - one accent per meaning
  - no emoji
- **Layout:** max width about 1280px; two columns on desktop, one column under 900px. No horizontal scroll at 390px.

---

## 5. Implementation Notes

- **Files:** build `app/story.html`, `app/story.css`, `app/story.js` next to the current page, reading the same `data/demo.js`. Leave `index.html` alone until the new page is approved, then swap.
- **No build step,** vanilla JS, works when opened with `file://`.
- **Derive everything from `window.COMMONWATT`.** Only the copy is hardcoded. If `demo.js` is missing, show "Run `uv run commonwatt-demo` first."
- **Replay engine:** build a chapter list by scanning the log (section 2), then play messages within each chapter at the chosen speed. Batch asks and offers. Pause automatically for about 2 s on each key-moment card.
- **Reuse clay drawing code** from `docs/reference/commonwatt-story.html`: the isometric projection `P(b, x, y, z)`, `box`, `quad`, `winX`, `winY`, and the material CSS variables.
- **Accessibility:** keyboard controls for the replay, visible focus, `prefers-reduced-motion` (jump instead of animate), text alternatives for the charts.
- **Keep `#all`** (or an equivalent) to show the final state immediately, for screenshots and judges in a hurry.
- **Check before shipping:** Playwright screenshots at 1440px and 390px wide, no console errors, no horizontal overflow, and every number on screen traced to a field in `demo.js`.

---

## 6. Copy Rules

- Plain words: "asked," "offered," "accepted," "countered," "declined," "blocked by its guard," "paid."
- Say "simulated" or "assumption" wherever it applies; results are simulation outputs, not measured savings.
- Members are large buildings, households, small businesses, and public institutions. No EVs.

---

## 7. Priority Order (if time runs short, stop after any step)

1. **Hero and the alone-vs-together chart** (sections 3.1 and 3.3). This alone fixes the biggest problem.
2. **Inside one building** (3.5): the privacy story.
3. **The replay** (3.4): the clustered network, one message at a time, the pooled meter, and key-moment cards.
4. **Context strip, fairness, and appendix** (3.2, 3.6, 3.7).
5. **Swap** `story.html` in as `index.html`, and update the README screenshots in `docs/`.
