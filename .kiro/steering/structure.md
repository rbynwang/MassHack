# Project structure

```
data/housezero/     Source dataset (read-only, see its README)
proposal/           Pitch page for the team
src/masshack/       Python package
  data.py           Loading, cleaning, train/test split by date
  forecast.py       Path 1 load/PV forecaster
  battery.py        Battery + tariff physics (exact equations)
  planner.py        LP / CEM planners
  world_model.py    Path 2 latent model
src/commonwatt/     Agent network: protocol, network (bus/registry), trust (guards/ledger), agents/, tools/
  tools/contract.py The only interface between agents and the ML model (EnergyModelTool)
app/                Static site: index (landing), story (network replay), history, member, about, presentation/ (3D scenes);
                    shared nav in app/nav.js; data in app/data/demo.js (`uv run commonwatt-demo`) and week.js (`uv run commonwatt-week`)
protocol/schemas/   JSON Schemas of the 7 protocol messages (generated)
src/homesim/        Synthetic single-family home generator (config.yaml + seed; `uv run homesim`)
data/baseline/      Public calibration baselines (National Grid R-1, Eversource, ResStock, EIA)
data/synthetic/     Generated homesim datasets (gitignored; regenerate from config + seed)
scripts/            Entry points: train, backtest, export demo JSON
demo/               Static demo page + exported JSON
tests/              pytest + hypothesis
.kiro/              Steering, specs and hooks (required by event rules — never gitignore)
KIRO_USAGE.md       Running log of how Kiro was used (feeds the submission write-up)
```

## Conventions
- snake_case modules and functions; type hints on public functions.
- Power is kW, energy is kWh; put the unit in column and variable names
  (`load_kw`, `soc_kwh`).
- Timestamps are UTC internally; convert to America/New_York only for display.
- Small commits with clear messages; push often so the team stays in sync.
