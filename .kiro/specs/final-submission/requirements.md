# Final submission — requirements

Deadline: submitted on SundAI by **8:00 PM ET, Oct 24 2026**. Plan built at 6:30 PM; every task is time-boxed.
Track: **Climate Tech (Energy & Climate), challenge C3**: "clean power still has to show up at the peak".

## Hard requirements from the rules (missing any one can disqualify)

1. WHEN judges open the GitHub link THE repository SHALL be **public**, contain all source, assets and
   instructions to run the project, and keep `/.kiro` at the root (never gitignored).
2. THE submission SHALL include a **demo video under 3 minutes**, public on YouTube or Vimeo, with no
   third-party trademarks, battery or device brand names, or copyrighted music.
3. THE submission SHALL link to a **working demo** (GitHub Pages site of `app/`).
4. THE submission SHALL name the track and include a **write-up of how Kiro was used** (IDE/CLI/Web/Crew,
   specs, hooks, steering, MCP, property-based tests, powers).
5. Every number on screen SHALL be labeled measured, simulated or assumption; Massachusetts data only.

## Product requirements (what makes it competitive)

### R1 About page
- THE site SHALL have an About page with the problem statement, who it serves, and how it works.
- THE About page SHALL include a project architecture diagram (data → ML model tool → member agents →
  trust guards → coordinator → grid agent; signed bus; receipts ledger) drawn as inline SVG.
- THE About page SHALL show a "Planned next" card for the community planner / distribution utility view
  (neighborhood demand forecast from the ML model, feeder headroom, upcoming events), clearly marked planned.

### R2 Multi-node agent network (exists — polish only)
- THE network replay (`app/story.html`) SHALL stay the centerpiece; WHEN a user opens a member from the
  trading history or the phone view THE replay SHALL be reachable in one click.

### R3 Seven-day trading history with audit trail
- THE system SHALL simulate the week **June 20–26, 2025** (event days from
  `data/training_2025_2026/dr_events_2025.csv`: Jun 20, 23, 24, 25, 26; Jun 21–22 have no event).
- FOR each day THE system SHALL record: ask kW and window, pooled kW, delivered kWh, payments, peak with
  and without the commons, members paid, rounds, blocked requests (with reason), and every receipt.
- THE Trading history panel SHALL show a 7-day chart (delivered kWh and $ per day; peak alone vs. together),
  a sortable member × day earnings table grouped by member type, and an **audit trail**: each receipt's
  id, member, kWh, $, `prev_hash` → hash, signature status, with a "verify chain" result.
- WHEN a day is selected THE panel SHALL show that day's negotiation summary and link to its replay.
- THE week data SHALL be labeled **simulated** (synthetic DR schedule, real weather/load inputs).

### R4 Member phone view (end user)
- THE site SHALL show a phone-sized panel (390 × 844) for one member at a time, with a picker for
  member type: household, household with EV, small business, public institution, large building.
- THE phone view SHALL show: the building (pre-rendered 3D still from `app/presentation/renders/`, cropped),
  live power in/out with the flow direction, battery or EV charge, the ongoing negotiation (request →
  counter/accept/blocked with reason), private limits (marked "never shared"), today's earnings and a
  7-day earnings list from R3.
- THE phone view SHALL use the member's real data from `app/data/demo.json` / `week.json`.

### R5 One site, one navigation
- THE site SHALL have a shared top nav: **Scenes** (3D story) · **Network** (replay) · **Trading history**
  · **Member app** · **About**. All pages work offline from files and on GitHub Pages.

### R6 Repo quality
- `README.md` SHALL explain the problem, the demo link, how to run (`uv sync`, `uv run commonwatt-demo`,
  `uv run commonwatt-week`, `uv run pytest`, open `app/index.html`), data sources and licenses
  (HouseZero CC BY 4.0 with both DOIs), team, and the Kiro write-up link.
- `uv run pytest` SHALL pass, including property-based tests for the week ledger.
