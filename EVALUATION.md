# Model evaluation: what limited the results, and what fixed it

Every number below comes from `app/public/demo.json` (the pipeline run) and the scripts in `eval/`. "Before" is the build delivered at 15:10; "now" is the current build.

## 1. Where the money was lost: forecast or planner?

Test: give each battery's hourly re-planner a *perfect* forecast (`eval/planner_gap.py`). If it then captures ~100% of the best possible savings, the planner is fine and every lost dollar is forecast error.

| Share of best-possible battery savings captured (51 building batteries) | Winter | Summer |
|---|---|---|
| Hourly re-planning with a perfect forecast | 99% | 102% |
| Hourly re-planning with the forecast we had (before) | 63% | 51% |

**Finding:** the optimizer is not the problem. The gap is forecast error, and it is magnified by the tariff: a demand charge bills the single highest hour, so a 5% miss on a building's peak can cost half of that day's battery saving.

## 2. Four directions tested, two rejected

| Direction | Test | Result |
|---|---|---|
| Tune how the re-planner corrects forecast errors during the day | error-correction decay 0, 0.6, 0.9 (`eval/planner_variants.py`) | no gain (49–51% summer, 61–63% winter) — **rejected** |
| One pooled LightGBM per building group instead of one per building | ~104 held-out days (`eval/forecast_eval.py`) | worse for commercial buildings (8.6% vs 6.1% error) — **rejected** |
| Plan against forecast *scenarios* (stochastic MPC) instead of one forecast line | same forecasts, same days | summer 51% → 67%, winter 63% → 79% — **adopted** |
| Calibrate the P10–P90 band per building group on separate weeks | ~104 held-out days | coverage 52–78% → 76–84% of hours (target 80%) — **adopted** |

## 3. The action-effect problem was in the data, not the model

Before, the world model's predicted effect of *load shift* had ~0 correlation with what happened. Inspecting the data showed why: each building's normal run and its load-shift run came from two **separately fitted** models, so their difference was the true effect plus two independent fitting errors. For load shift the noise was about twice the real effect (true paired effect ≈1.2% of a building's load; the old difference ≈2.4%). No model can learn that.

**Fix** (`eval/fix_modes.py`): fit each action's effect directly on the *paired* source simulations (same building, same hour, with and without the action), drive it with the measured 2025–26 weather, and add it to the building's normal run. Then train an effect model on the paired difference and let each action use whichever model predicts it best on held-out days.

| Action | Model | Building-days | Error, % of peak | Shape match (corr.) | Right direction at peak | Used |
|---|---|---|---|---|---|---|
| ev_delay | delta_lgbm | 1115 | 15.11 | 0.58 | 70% | ✓ |
| ev_delay | none | 1115 | 15.44 | – | – |  |
| ev_delay | world_model | 1115 | 16.20 | 0.62 | 95% |  |
| hvac_curtail | delta_lgbm | 18 | 0.80 | 0.63 | 0% |  |
| hvac_curtail | none | 18 | 0.76 | – | – | ✓ |
| hvac_curtail | world_model | 18 | 2.46 | -0.02 | 6% |  |
| load_shift_33 | delta_lgbm | 2912 | 0.44 | 0.66 | 65% | ✓ |
| load_shift_33 | none | 2912 | 0.52 | – | – |  |
| load_shift_33 | world_model | 2912 | 1.77 | 0.21 | 45% |  |
| precool_42 | delta_lgbm | 4992 | 1.04 | 0.97 | 85% | ✓ |
| precool_42 | none | 4992 | 2.51 | – | – |  |
| precool_42 | world_model | 4992 | 2.90 | 0.69 | 62% |  |
| thermal_preheat | delta_lgbm | 11 | 0.90 | 0.91 | 46% | ✓ |
| thermal_preheat | none | 11 | 1.01 | – | – |  |
| thermal_preheat | world_model | 11 | 2.29 | 0.15 | 9% |  |

EV delay stays hard: when a car plugs in is random day to day, so a model can only learn the average effect (it barely beats "no change").

## 4. Forecast accuracy now (≈104 held-out days, every season)

Train 193 days · calibration 90 · test 104. The planner's final models are then refit on every day except the two peak weeks.

| Model | Winter % | Summer % | Spring/fall % | Peak-hour % | Coverage |
|---|---|---|---|---|---|
| LightGBM, calibrated (used) | 13.5 | 16.4 | 15.3 | 19.6 | 80% |
| LightGBM, uncalibrated | 13.5 | 16.4 | 15.3 | 19.6 | 66% |
| World model (JEPA-style) | 20.0 | 22.5 | 21.9 | 25.8 | 79% |
| LightGBM, no weather | 16.1 | 21.2 | 17.8 | 21.6 | 66% |
| Same hour last week | 21.9 | 31.4 | 25.6 | 24.5 | 6% |

Whole community: 4.0% error, peak hour 3.7%. By group (LightGBM): civic 6.1%, civic_measured 5.2%, home 31.7%, housezero 9.1%, large_retail 6.6%, small_business 6.3%.

The world model is less accurate than per-building LightGBM for normal load; we keep it in the evaluation and say so.

## 5. What changed in the results

| | Winter before | Winter now | Summer before | Summer now |
|---|---|---|---|---|
| Batteries alone: community peak kW | 13,419 | 13,067 | 13,794 | 13,833 |
| Collective: community peak kW | 13,536 | 13,215 | 13,867 | 13,733 |
| Collective: avg import in grid-need hours kW | 11,698 | 11,848 | 11,607 | 11,476 |
| Batteries alone: community bills $ | 211,612 | 207,470 | 209,256 | 207,090 |
| Collective: community bills $ | 211,752 | 207,671 | 209,708 | 206,835 |

For reference, no battery: winter peak 14,089 kW, summer 13,969 kW; perfect-foresight batteries alone: 12,973 / 13,511 kW.

| Planner capture of best-possible savings (current forecasts) | Winter | Summer |
|---|---|---|
| Perfect forecast | 99% | 102% |
| One forecast line | 62% | 47% |
| Forecast scenarios (used) | 78% | 66% |

## 6. What would move the needle next
1. **Better peak-day forecasts are worth real money**: the planner with a perfect forecast captures ~100%, with ours ~60–80%. Next candidates: intraday re-forecasting each hour with the latest meter reading (hour-ahead models are far more accurate than day-ahead), and a loss that weights the top hours of each day.
2. **More measured buildings**: two of 116 members are metered; the rest are physics templates. Real meters would test the forecasts where it matters.
3. **EV timing** needs plug-in data (charger telemetry), not more modelling.
