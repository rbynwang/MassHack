# How we used Kiro

Running notes for the Hackachusetts submission write-up ("Provide a write up on
how Kiro was used"). Fill the sections at the end; append to the log as you go.

## Log

| Time (ET) | Who | Kiro feature | What and why |
| --- | --- | --- | --- |
| 10/24 ~10:00 | Robyn | Steering | Drafted `product.md`, `tech.md`, `structure.md` and a `fileMatch` steering doc (`housezero-data.md`) with Claude Code from our proposal and the dataset README, so Kiro knows the meter semantics and avoids data leakage in backtests. |
| 10/24 ~10:00 | Robyn | Hooks | Added `py-compile-on-save` (PostFileSave) and `usage-log-on-stop` (Stop) hooks. |
| 10/24 ~13:00 | Kiro | Vibe session + steering | Reviewed the synthetic household data guideline against HouseZero, pulled public baselines (National Grid R-1 2023–2026, Eversource, NREL ResStock MA single-family, EIA), built `src/homesim` (guideline steps 1–2) and generated two 200-home dev sets with calibration checks. Updated `structure.md` with the new package and data folders. |
| 10/24 ~15:20 | Kiro | Spec + steering | Wrote `.kiro/specs/commonwatt-network/` (requirements with EARS criteria, design, 13 tasks) and rewrote `product.md` for the Commonwatt pivot, including the split of work (ML model by Robyn, agent network by Kiro) and the "Massachusetts data only" rule. |
| 10/24 ~15:50 | Kiro | Spec tasks 1–12 | Implemented the agent network from the spec: protocol (7 messages, JSON Schemas), signed bus, registry with live join, trust guards with hash-chained receipts, member/coordinator/grid agents behind one model-tool contract, the June 24, 2025 scenario and the offline demo page. |
| 10/24 ~15:55 | Kiro | Property-based tests | `tests/test_commonwatt.py` (hypothesis): guard never passes a request over the owner's limit; members never accept more than they can hold or drain below reserve; pooled ≤ accepted; payouts add up; tampered receipts and forged envelopes are caught. PBT caught a rounding bug: a member countered 4.53 kW when it could hold 4.529 kW; fixed by rounding promises down. |
| 10/24 ~15:58 | Kiro | Hook | `commonwatt-tests-on-save` (PostFileSave on `src/commonwatt/*.py`) reruns the network's property-based tests on every change. |
| 10/24 ~18:10 | Kiro | Spec task 13 | Plugged the trained GridCollective model into the agents as their default tool (`tools/gridcollective.py`): member agents use its calibrated LightGBM forecasts and battery LP to price and accept, counter or decline each request. |
| 10/24 ~18:28 | Kiro | Steering + git | Committed the 3D presentation scenes from the other session to `app/presentation/` and added a `fileMatch` steering doc (`.kiro/steering/presentation.md`) that pulls in the presentation's README whenever those files are edited. Merged `kiro/commonwatt` into `main` through a pull request. |
| 10/24 ~18:37 | Kiro | Spec task 1 (final-submission) | Shared nav (`app/nav.js`) on every page including the 3D scene player; `app/index.html` is now a landing page reading the June 24 numbers from `demo.js` (old dashboard kept as `dashboard-v1.html`). `scripts/check_story.py` now opens every page at 1440 and 390 px and fails on console errors, overflow or a missing nav. |
| 10/24 ~18:38 | Kiro | Spec task 2 (final-submission) | Wrote `README.md`: problem, live-demo link, layer table, June 24 results (simulated), quick start incl. `commonwatt-week`, site and repo maps, data table with labels and both HouseZero DOIs. |
| 10/24 ~18:38 | Kiro | Spec task 3 (final-submission) | Filled the write-up below (`## Write-up`): tools, both specs, the three hooks, steering incl. the two fileMatch docs, MCP and powers (none, stated plainly), PBT and the 4.53 vs 4.529 kW bug, and the Claude/Kiro split. |
| 10/24 ~18:38 | Kiro | Spec task 4 (final-submission) | Added `.github/workflows/pages.yml`: on push to `main`, uploads `app/` with `actions/upload-pages-artifact` and deploys with `actions/deploy-pages`. |
| 10/24 ~18:48 | Kiro | Spec task 5 (final-submission) | Made the day a parameter (`build_neighborhood(day)`, `run(..., day, ledger, library, guard_keys)`) instead of the fallback, and added `commonwatt-week`: June 20–26, 2025, 5 event days from the synthetic DR schedule, ask scaled by ISO-NE load (60 kW on June 24), one hash-chained ledger and one guard key per member for the whole week. Result: 52 receipts, chain verifies, $189.35 paid (simulated). On June 20 and 26 the Boston-zone price was below every member's cost, so all members declined. |
| 10/24 ~18:47 | Kiro | Spec task 6 (final-submission), property-based tests | `tests/test_week.py` (hypothesis): weekly payouts = sum of receipts; the week-long chain verifies and links across days; changing any field of any receipt breaks it; nobody is paid on a day without an ask; receipts never pay for more than was committed; the exported canonical text hashes to the recorded hash (what the browser re-checks). 16 tests pass. |
| 10/24 ~18:50 | Kiro | Spec task 7 (final-submission) | `app/history.html`: week totals, 7-day charts (delivered kWh and $; peak alone vs. together), a day picker with each day's blocked, countered and declined requests, a sortable member × day earnings table grouped by kind, and an audit trail whose "Verify chain" button recomputes all 52 SHA-256 hashes and checks all 52 Ed25519 signatures in the browser. All labeled simulated. |
| 10/24 ~18:30 | Robyn + Claude Code | Spec | Drafted `.kiro/specs/final-submission/` (requirements with the rules' hard requirements, design with site map, week-simulation data shape, video script and form text; 12 time-boxed tasks) for Kiro to execute before the 8 PM deadline. Added the pre-rendered 3D scenes to `app/presentation/` (built with a three.js kit and baked to stills so the page needs no WebGL). |

## Write-up

### Kiro tools used
We used the **Kiro IDE** throughout, in Autopilot mode, across several chat sessions that shared one repository.
One session built the agent network and the site; another, run alongside it, built the 3D presentation scenes and
drafted the final-submission spec. A workspace `permissions.yaml` let Kiro run shell commands without prompting
while denying destructive ones (`rm -rf`, force push, `git reset --hard`); it blocked one `rm -rf` during the day,
as intended.

### Spec-driven development
Two specs in `.kiro/specs/`, each with `requirements.md` (user stories with EARS acceptance criteria),
`design.md` and `tasks.md`:
- **`commonwatt-network`** (13 tasks, all done): protocol, signed bus, registry with live join, trust guards and a
  hash-chained ledger, member, coordinator and grid agents behind one model-tool contract, the June 24 scenario,
  the demo page, property-based tests, a hook, and finally plugging in the team's trained model as the agents' tool.
  The tool contract (`src/commonwatt/tools/contract.py`) was the first thing written, so the ML work and the agent
  work could proceed in parallel and meet at a single interface.
- **`final-submission`**: the hackathon's hard requirements as acceptance criteria, a site map, the week-simulation
  data shape, the video script and form text, and time-boxed tasks with fallbacks. Kiro executed it top to bottom,
  committing after each task.
Compared with vibe coding, specs kept a one-day build honest: every task had a "done when" check, and the
requirements forced labels (measured / simulated / assumption) onto every number.

### Agent hooks
`.kiro/hooks/`:
- `commonwatt-tests-on-save` (PostFileSave on `src/commonwatt/*.py`): reruns the network's property-based tests on
  every change.
- `py-compile-on-save` (PostFileSave on `*.py`): catches syntax errors as soon as a file is saved.
- `usage-log-on-stop` (Stop): after each notable turn, reminds Kiro to append a row to the log above. Most rows in
  this log were written because of it.

### Steering docs
`.kiro/steering/`: `product.md` (what Commonwatt is, the split of work, "Massachusetts data only", "label every
number"), `tech.md` (stack, offline, battery and tariff math are exact, never learned), `structure.md` (repo map,
units in names, UTC internally), and two `fileMatch` docs that load only when relevant: `housezero-data.md`
(meter semantics: net grid power is not demand, PV night noise, no future data in backtests, cite both DOIs) for
`src/**`, `data/**`; and `presentation.md`, which pulls the 3D scenes' handoff notes into context when
`app/presentation/**` is edited. The data rules made the biggest difference: Kiro never summed overlapping meters
or used out-of-state data, and it labeled assumptions without being asked.

### MCP
We did not add any MCP servers for this build.

### Property-based testing
`tests/test_commonwatt.py` and `tests/test_week.py` (hypothesis):
- a trust guard never passes a request over the owner's limit or outside allowed hours;
- a member never accepts more than it can hold for the whole window, never drains its battery below the reserve,
  and declines when the price is below its cost;
- the pooled commitment never exceeds the sum of accepted amounts; payouts add up to settled earnings;
- a changed receipt or a forged envelope is detected; the week-long receipt chain verifies, and tampering with any
  receipt breaks it.
PBT caught a real bug that example tests missed: a member countered **4.53 kW** when it could only hold
**4.529 kW**, because the promise was rounded to the nearest 0.01 kW. Promises are now rounded down.

### Kiro powers
We did not use Kiro powers.

### Kiro + Claude workflow
Claude Code drafted: the steering docs, the final-submission spec, data exploration, and the 3D presentation kit
and scenes. Kiro executed: both specs task by task, the agent network, the trained-model integration, the site,
the tests and hooks, and all git work (commits, branches, the pull request into `main`). Every change to the
repository went through Kiro, so this log and the commit history record how it was built.
