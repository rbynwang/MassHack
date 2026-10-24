---
inclusion: always
---
# Tech stack and constraints

- Everything runs on one Apple-silicon Mac. No cloud training.
- Python 3.11+, pandas, pyarrow, numpy, scikit-learn, lightgbm, torch (use the `mps` device when available, else CPU), cvxpy for the optimal baseline, pvlib for solar.
- Front end: one static web page (HTML + vanilla JS or a small Vite app) that reads JSON exported by `model/export_demo.py`. No server needed for the demo.
- Optional explanation layer: an LLM call that receives numbers from the world model and only explains them. The LLM never chooses actions.

## Data (period rule: everything shown is 2025-05-01 to 2026-06-01, America/New_York)
All data lives in `data/` and is read only through `data/load_dataset.py`:
- `weather.parquet`: measured HouseZero weather, 15-min, gaps filled and flagged; `pv_per_kwdc` solar curve.
- `grid.parquet`: ISO-NE real-time price (.Z.NEMASSBOST, $/MWh) and system load (MW); `grid_stress`, `price_spike` flags.
- `members.csv` + `members_load_2025_2026.parquet`: one row per member; `group` is housezero, civic_measured (BPL Central), civic, large_retail, small_business or home; `in_community=False` marks the 200 training-only homes. `source` is `measured`, `simulated_template_hz_weather` (NREL ComStock designs driven by HouseZero's measured weather) or `synthetic_homesim`. Modes include `baseline`, `load_shift_33`, `precool_42` (raises the midday peak: never offered), `thermal_preheat`, `hvac_curtail`, `ev_delay` (homes with EVs).
- `boston_stock.csv`: BERDO 2026 (2025 data) building counts, floor area and kWh by zip and archetype. Covers buildings >= 20,000 sq ft.
- `dr_events_2025.csv`: synthetic ConnectedSolutions-style event days (label as synthetic).
- Original HouseZero files in `data/housezero/` stay untouched.
- Never load or display any pre-2025 data. The only weather source is HouseZero's measured 2025–26 weather station. ComStock building designs were used only as physics templates during data preparation; no 2018 timestamps or weather are in `data/`.
- Timestamps: UTC, interval start, 15 minutes. Convert to America/New_York only for display, tariffs and event windows.

## Rules
- Report every number with its unit (kW vs kWh vs $).
- Battery physics and the tariff are exact equations in `model/physics.py`, never learned.
- Seed every random generator; training must be reproducible in under 30 minutes on the Mac.
