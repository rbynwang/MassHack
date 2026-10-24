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
