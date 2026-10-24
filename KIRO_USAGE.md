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
| 10/24 ~18:30 | Robyn + Claude Code | Spec | Drafted `.kiro/specs/final-submission/` (requirements with the rules' hard requirements, design with site map, week-simulation data shape, video script and form text; 12 time-boxed tasks) for Kiro to execute before the 8 PM deadline. Added the pre-rendered 3D scenes to `app/presentation/` (built with a three.js kit and baked to stills so the page needs no WebGL). |

## Write-up sections (fill before 6 PM)

### Kiro tools used
IDE / CLI / Web / Crew: which ones, and how they differed.

### Spec-driven development
How we structured specs; how it compared to vibe coding.

### Agent hooks
Which workflows we automated, and what that changed.

### Steering docs
Strategy, and what made the biggest difference to Kiro's responses.

### MCP
Servers added, and what they let us do that was otherwise hard.

### Property-based testing
Which requirements had PBT; issues it caught that unit tests missed.

### Kiro powers
Which powers we used; any third-party tooling they brought in.

### Kiro + Claude workflow
How Claude Code (drafting specs/steering, data exploration, review) and Kiro
(executing specs, hooks, git) worked together.
