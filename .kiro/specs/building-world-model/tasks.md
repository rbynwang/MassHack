# Implementation plan

Status key: [x] built and tested in the starter code, [ ] open for the team in Kiro.

- [x] 1. Data loading
  - [x] 1.1 `masshack/data.py` loads weather, grid, members and member loads through `data/load_dataset.py`; `tests/test_period.py` asserts every timestamp is within 2025-05-01..2026-06-01 local. _Requirements: 1.1_
  - [x] 1.2 `data/tariff.json` (example MA G-2 rate) and `dr_events_2025.csv` with local event windows. _Requirements: 3.1_
- [x] 2. Physics and baselines
  - [x] 2.1 `masshack/physics.py` battery + bill with tests (energy balance, SOC limits, demand charge on the monthly max). _Requirements: 2.2, 3.1_
  - [x] 2.2 `masshack/optimizer.py`: own-bill LP, vendor default; perfect foresight in `simulate.py`. _Requirements: 3.1, 3.2_
- [x] 3. Forecast models
  - [x] 3.1 Day-ahead weather forecast without leakage (`data.weather_forecast`). _Requirements: 1.2_
  - [x] 3.2 LightGBM quantile forecaster and seasonal naive (`masshack/forecast.py`). _Requirements: 1.1, 1.3_
  - [x] 3.3 JEPA-style world model with member embeddings (`masshack/world_model.py`). _Requirements: 1.1, 2.1_
- [x] 4. Planner
  - [x] 4.1 Battery plan against a cautious forecast (P50 energy, P90 peak protection). _Requirements: 2.1–2.3_
  - [x] 4.2 Building modes (load shift, pre-cool, pre-heat, HVAC curtail) as flex offers with rebound. _Requirements: 2.4_
- [x] 5. Evaluation
  - [x] 5.1 Five strategies on the winter and summer peak days (`run_all.py`). _Requirements: 3.1–3.3_
  - [x] 5.2 Forecast metrics on held-out peak weeks, plus the no-weather ablation. _Requirements: 1.3_
- [x] 6. Demo
  - [x] 6.1–6.4 `app/public/index.html` reads `demo.json`: layers, day view, hour inspector, member view, forecast table, latent map, Boston, data sources. _Requirements: 4.1–4.4_
- [ ] 7. Next steps for the team (run in Kiro)
  - [ ] 7.1 Replace the example tariff with the current Eversource G-2 numbers in `data/tariff.json` and re-run `python run_all.py`. _Requirements: 3.2_
  - [ ] 7.2 Add a plain-language explanation for each battery decision (one sentence with its dollar value) to the member view. _Requirements: 4.3_
  - [x] 7.3 Temperature what-if: the summer peak day re-planned with the forecast shifted −10, −5, 0, +3 °C (demo section 6). _Requirements: 4.2_
  - [x] 7.4 Hourly re-planning on actual load with forecast-bias correction (`optimizer.mpc_realize`). _Requirements: 2.3_
  - [x] 7.6 Building-type embeddings + type-balanced training; 200 training-only homes with noise and gaps. _Requirements: 1.1_
  - [x] 7.7 Hybrid planner forecaster: LightGBM baseline + world-model action effects (`forecast.HybridForecaster`). _Requirements: 2.1_
  - [x] 7.8 Evaluation on ~104 held-out days (`eval/`): planner with a perfect forecast captures ~100% of savings, so the gap is forecast error. _Requirements: 1.3, 3.1_
  - [x] 7.9 Stochastic MPC: re-plan hourly against forecast scenarios (`optimizer.mpc_realize_robust`). _Requirements: 2.3_
  - [x] 7.10 Rebuild action runs from paired source differences (`unified_build/fix_modes.py`); paired-difference effect model (`forecast_v2.DeltaModel`), chosen per action on held-out days. _Requirements: 2.4_
  - [x] 7.11 Calibrated P10–P90 bands per building group (`forecast_v2.Calibrated`). _Requirements: 1.3_
  - [ ] 7.5 Record the demo video and freeze at 17:30.
