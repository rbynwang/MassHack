# Final submission — tasks

Work top to bottom. P0 tasks are required to submit; do them first even if features slip.
After each task: run `uv run pytest -q`, commit with a clear message, and add a line to `KIRO_USAGE.md`.
**Stop all feature work at 7:15 PM ET** and move to tasks 10–12.

## P0 — required (start now)

- [x] 1. **Integrate the 3D scenes and shared nav** (10 min)
  - `app/presentation/` is already in the working tree (player `commonwatt-story.html`, renders, kit, renderer, live view, README).
  - Add `app/nav.js` (Scenes · Network · Trading history · Member app · About) and include it in
    `app/presentation/commonwatt-story.html`, `app/story.html` and every new page. Make `app/index.html` the landing page
    (pitch, Jun 24 hero numbers from `demo.js`, five links). Open each page from `file://` and check the
    console is clean.
- [x] 2. **README.md** (10 min) — currently empty. Problem, demo link placeholder, screenshots
  (`docs/*.png`), quick start (`uv sync`, `uv run commonwatt-demo`, `uv run commonwatt-week`,
  `uv run pytest`, open `app/index.html`), repo map (from `.kiro/steering/structure.md`), data and
  licenses (HouseZero CC BY 4.0 + both DOIs, BPL, ISO-NE, synthetic DR schedule labeled), labels policy
  (measured / simulated / assumption), team, link to the Kiro write-up. Track: Climate Tech C3.
- [x] 3. **Kiro write-up** (10 min) — fill every section under "Write-up sections" in `KIRO_USAGE.md`
  from the log: steering (fileMatch data rules), spec-driven agent network (13 tasks), hooks (tests on
  save, usage log on stop), PBT (the 4.53 vs 4.529 kW rounding bug), MCP (say honestly if none were
  used), Kiro + Claude workflow (Claude drafted steering/specs/3D scenes; Kiro executed specs and owns
  git). Rename the heading to `## Write-up` so the README can link to it.
- [x] 4. **GitHub Pages workflow** (5 min) — add `.github/workflows/pages.yml` that uploads `app/` with
  `actions/upload-pages-artifact` and deploys with `actions/deploy-pages` on push to `main`.

## P1 — features (6:45–7:15 PM, run in parallel if possible)

- [x] 5. **Week simulation** (25 min, see design R3 incl. fallback) — `src/commonwatt/week.py`,
  `commonwatt-week` script, `app/data/week.json` + `week.js`, receipts chained across days.
- [x] 6. **PBT for the week ledger** (5 min) — `tests/test_week.py` (design R3 list).
- [x] 7. **Trading history page** `app/history.html` (20 min) — 7-day chart (Plotly is vendored), day
  picker with that day's summary and blocked requests, member × day earnings table grouped by type,
  audit trail table with hash chain and "verify chain" (recompute in JS from `week.js`). Label simulated.
- [x] 8. **Member app page** `app/member.html` (20 min) — phone frame, picker of five members, sections in
  design R4, "See it in the network" link to `story.html#replay`.
- [x] 9. **About page** `app/about.html` (15 min) — problem, solution, inline SVG architecture diagram,
  "Planned next: planner / utility view" card (ML neighborhood forecast, feeder headroom), team, data
  credits.

## P0 — ship (7:15 PM onward, no exceptions)

- [ ] 10. **Merge and publish** (5 min) — merge `kiro/commonwatt` into `main`, push. (Robyn: make the repo
  public and enable Pages → Source: GitHub Actions. Check the site loads.)
- [ ] 11. **Record the video** (20 min, Robyn) — follow the script in design.md, ≤ 3:00, upload to
  YouTube as Public. No brand names on screen.
- [ ] 12. **Submit on SundAI** (10 min, Robyn) — form text in design.md; paste GitHub, demo, video and
  write-up links; pick Climate Tech; confirm by 7:50 PM.
