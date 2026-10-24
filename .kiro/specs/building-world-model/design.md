# Design: Building World Model

## Data (2025-05-01 to 2026-06-01 only)
| Table | Use | Notes |
|---|---|---|
| `members_load_2025_2026.parquet` (member `hz_main`) | Real test building: HouseZero, Cambridge, measured | Small (peak ~4.7 kW in winter), net-positive, heat pump. Also has indoor temperature and window/valve actions. |
| `members_load_2025_2026.parquet` (40 template members) | Variety across Boston building types (offices with chillers, restaurants with kitchens, strip malls with rooftop AC, gas heat), modes `baseline`, `load_shift_33`, `precool_42` | ComStock building designs driven by HouseZero's measured 2025–26 weather. Summer AC peaks drive the demand-charge story. |
| `weather.parquet` | Climate inputs and the solar curve | Measured at HouseZero. |
| `grid.parquet`, `dr_events_2025.csv` | Prices, grid stress, event days | ISO-NE real data; events synthetic. |
| `data/tariff.json` | Demand $/kW on the highest 15-min kW per month, energy $/kWh, fixed $/month | Example MA G-2 rate effective 2026-04-01. |

## Components
1. `model/features.py`: calendar features (hour, weekday, holiday), weather features, lags; simulated weather forecast = measured + noise.
2. `model/physics.py`: battery (capacity kWh, power kW, round-trip efficiency 90%, SOC limits 10–95%) and bill calculation. Exact, unit-tested.
3. `model/baselines.py`: no battery; vendor default (charge from surplus solar, discharge whenever load > solar); TOU rule; perfect-foresight LP (cvxpy).
4. `model/world_model.py`: encoder (MLP or small 1-D conv over 24 h history + weather) → latent z (32); predictor z_{t+1} = f(z_t, a_t, w_{t+1}); heads → load, solar quantiles. Loss: quantile loss on heads + latent prediction loss against an EMA target encoder (JEPA-style) + small variance regularizer. Fallback: LightGBM quantile models behind the same interface.
5. `model/planner.py`: cross-entropy method, 64–256 candidate battery schedules (+ building mode where available), 3 iterations, cost = bill from physics on imagined trajectories under P50 plus a peak penalty under P90.
6. `model/evaluate.py`: rolling simulation over test days for all strategies; writes `results/metrics.json` and figures.
7. `model/export_demo.py`: writes `app/public/demo.json` (selected days, all strategy traces, imagined plans, explanations).
8. `app/`: single page; views A (imagine → reality), B (temperature slider), C (latent map), plus headline numbers.

## Interfaces
- `forecast(history_df, weather_fc_df) -> DataFrame[p10,p50,p90 for load_kw, pv_kw]`
- `rollout(z0, actions, weather_fc) -> DataFrame` (imagined trajectory)
- `plan(state, weather_fc, tariff, battery) -> (action_now, chosen_plan, candidate_plans, explanation_numbers)`

## Risks and fallbacks
- World model underperforms LightGBM: present both and keep the better one in the planner; the latent map still shows what the model learned.
- All tables are 15-min; keep a `dt_hours` parameter so hourly runs also work.
- Time: freeze the demo at 17:30.
