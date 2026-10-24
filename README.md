# GridCollective Boston (MassHack, Track 3 Climate Tech)

Boston buildings that think ahead together. Each building forecasts its own electricity from the weather, plans its battery for its own bill, and offers the extra help it can give. A coordinator pools those offers when the grid needs help, a trust layer enforces every member's limits in code and signs a receipt for each action, and the money is split by contribution.

> **Agents and new teammates: start with [`AGENTS.md`](AGENTS.md)** (file map, data flow, rules, current numbers). Data columns: [`data/model_inputs/README.md`](data/model_inputs/README.md). Model evaluation: [`EVALUATION.md`](EVALUATION.md).

All data covers **2025-05-01 to 2026-06-01** (America/New_York). HouseZero's measured weather is the only weather source.

## How it works (top to bottom)

```
Grid                     use less (DR event, ISO-NE top load/price hours)  /  soak up (cheap power while members export)
  │
Collective coordinator   round 1: solo plans · round 2: price signal on the community's peak hours, re-plan capped at
  │                      each member's own solo peak · merit-order assignment · rebound check · pro-rata payouts
Trust layer              limits in code (max kW, min battery, allowed hours, comfort band, mode permission)
  │                      heat-warning rule for cooling centers · Ed25519 signed, hash-chained receipts
Member agents            forecast: LightGBM baseline + world-model action effects (P10/P50/P90)
  │                      plan: battery LP (HiGHS) · act: hourly re-planning on actual load (MPC) · offer hourly flex + cost
Buildings (116)          HouseZero + BPL Central (measured) · 25 civic incl. museums, schools, fire, police
                         · 9 large retail · 40 small businesses · 40 homes (4 with batteries, 11 EVs)
```

## The machine-learning part

- **Normal-load forecast (used by the planner):** one LightGBM quantile model per building (P10/P50/P90) on the weather forecast, calendar and recent load. Its P10–P90 band is calibrated per building group on separate weeks so it really covers 80% of hours.
- **Action effects:** what each building mode (load shift, pre-cool, EV delay, pre-heat) does to the load, from a model trained on *paired* runs (same building, same weather, with and without the action). For each action, the pipeline picks whichever predicts best on held-out days: this model, the world model, or "assume no change".
- **World model (JEPA-style, PyTorch):** encoder + EMA target encoder + action-conditioned predictor with building and building-type embeddings, trained on 316 buildings. It is evaluated alongside the others; today it loses on accuracy, and the pipeline reports that rather than hiding it.
- **Planner:** each battery re-plans every hour against several forecast scenarios at once (a stochastic linear program), not a single forecast line, because a demand charge punishes under-forecasting the peak far more than over-forecasting it.
- **Evaluation (`eval/`, `EVALUATION.md`):** about 104 held-out days (one week every month + both peak weeks), calibration on another 90; planner checks with a perfect forecast to separate forecast error from planning error.
- **What-if:** shift the weather forecast (−10, −5, 0, +3 °C) and watch forecasts, the heat-warning rule, plans and the coordinator's assignments change.

## Run it

```bash
pip install -r requirements.txt
python run_all.py                                             # data/model_inputs -> app/public/demo.json     # ~20 minutes on 2 CPU cores; add --reuse to skip retraining
python eval/planner_variants.py app/forecast_cache.pkl         # planner check (feeds the demo on the next --reuse run)
python make_results.py                                        # writes RESULTS.md from demo.json
python eval/make_evaluation.py                                # writes EVALUATION.md
python -m http.server -d app/public 8000                      # open http://localhost:8000
python -m pytest -q                                           # 12 tests
```

## Data

| Input | Kind | Source |
|---|---|---|
| HouseZero building: electricity by circuit, solar, indoor | Measured | Harvard CGBC HouseZero 2025–26 dataset, DOI 10.6084/m9.figshare.32790984.v1, CC BY 4.0; May 2025 from the earlier release |
| Weather | Measured | HouseZero weather station (the only weather source) |
| Boston Public Library Central Library | Measured | 5-minute meter, City of Boston / Analyze Boston, PDDL |
| 25 civic + 9 large retail + 40 small business members | Simulated | NREL ComStock 2025 Release 3 Boston building designs used as physics templates, driven by the measured weather |
| 40 community homes + 200 training-only homes | Synthetic | Team's homesim generator (seed 42), evening peak calibrated toward National Grid R-1 |
| Grid | Measured | ISO-NE real-time hourly LMP (.Z.NEMASSBOST) and system load (via gridstatus) |
| Boston building stock | Reported | City of Boston BERDO 2026 disclosure (2025 data), buildings ≥ 20,000 sq ft |
| Tariff | Real rate | Town of Concord MA G-2 (OpenEI URDB) as a Massachusetts G-2 example; homes on a flat residential rate |
| Demand-response events | Synthetic | ConnectedSolutions-style days chosen from real ISO-NE peak load |
| Battery sizes, flex costs, DR pay | Assumptions | Labeled in code (`agents.py`, `simulate.py`) |

## Headline results (see RESULTS.md and EVALUATION.md)

- Forecast on ~104 held-out days: whole community 4.0% error (peak hour 3.7%); civic / retail / business 6–7%; BPL Central 5%; the P10–P90 band covers 80% of hours.
- Batteries capture 78% (winter) / 66% (summer) of the perfect-foresight savings, up from 62% / 47%. With a perfect forecast, the planner reaches 99–102%.
- Action effects (shape match): pre-cool 0.97, load shift 0.66 (was 0.21 before the data fix), EV delay 0.58.
- Peak days, collective vs no battery: community bills −9.3% (winter) / −5.3% (summer).

## Repository layout

```
run_all.py  make_results.py        pipeline + results writer
masshack/                          library: data, physics, optimizer (stochastic MPC), forecast, forecast_v2, world_model, agents, coordinator, trust, simulate, boston
eval/                              evaluation experiments + EVALUATION.md generator
app/public/                        demo page + demo.json        app/forecast_cache.pkl  (for --reuse)
data/model_inputs/                 model training data (see its README)
data/housezero/  data/boston_public_library/   teammates' original measured datasets
data_build/                        how data/model_inputs was built (provenance)
tests/  .kiro/                     tests, Kiro steering/specs/hooks
```

## How we build it with Kiro

See `HOW-WE-USE-KIRO.md`. Steering, specs and hooks live in `.kiro/`.

## Attribution

HouseZero data © Harvard Center for Green Buildings and Cities, CC BY 4.0; this project uses a transformed derivative and is not an official Harvard release. BPL meter data: City of Boston, PDDL. ComStock © Alliance for Sustainable Energy (NREL). BERDO data: City of Boston, Analyze Boston. Grid data: ISO New England.
