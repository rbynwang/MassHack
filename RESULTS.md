# Results (generated from app/public/demo.json by make_results.py)

Period: 2025-05-01 to 2026-06-01 (America/New_York). Planner forecaster: **lightgbm (calibrated) baseline + action effects (ev_delay: delta_lgbm, hvac_curtail: none, load_shift_33: delta_lgbm, precool_42: delta_lgbm, thermal_preheat: delta_lgbm)**. Community: 116 members; the world model also trained on 316 buildings including 200 training-only homes.

## Forecast accuracy on held-out days (day-ahead, noisy weather forecast, no future data)

Split by whole weeks: train 193 days · band calibration 90 days · test 104 days (one week in every month plus the week around each peak day).

| Model | Winter error % | Summer error % | Spring/fall error % | Peak-hour error % | P10–P90 coverage (target 80%) |
|---|---|---|---|---|---|
| World model (JEPA-style, calibrated) | 20.0 | 22.5 | 21.9 | 25.8 | 79% |
| LightGBM with weather (calibrated) | 13.5 | 16.4 | 15.3 | 19.6 | 80% |
| LightGBM, uncalibrated band | 13.5 | 16.4 | 15.3 | 19.6 | 66% |
| LightGBM without weather | 16.1 | 21.2 | 17.8 | 21.6 | 66% |
| Same hour last week | 21.9 | 31.4 | 25.6 | 24.5 | 6% |

Whole community (sum of all members): LightGBM 4.0% error, peak hour 3.7%; world model 6.3% / 5.4%.

Per-member error averages every member equally, so the 40 noisy single homes pull it up.

### By building group (both seasons)

| Group | World model % | LightGBM % | LightGBM no weather % | Last week % |
|---|---|---|---|---|
| civic | 11.3 | 6.1 | 10.5 | 13.3 |
| civic_measured | 7.3 | 5.2 | 5.2 | 7.0 |
| home | 39.6 | 31.7 | 31.9 | 49.2 |
| housezero | 10.3 | 9.1 | 9.5 | 13.9 |
| large_retail | 10.7 | 6.6 | 6.5 | 16.5 |
| small_business | 12.9 | 6.3 | 9.5 | 13.8 |

40 homes forecast together (their sum): LightGBM 18.8% · world model 26.1%.

## Action effects: does the model know what a building mode does? (held-out days)

| Action | Model | Building-days | Error, % of building peak | Shape match (median corr.) | Right direction at peak hour | Predicted / actual kW at peak, summed |
|---|---|---|---|---|---|---|
| ev_delay | delta_lgbm (used) | 1115 | 15.11 | 0.58 | 70% | -1,068 / -7,977 |
| ev_delay | none | 1115 | 15.44 | – | – | 0 / -7,977 |
| ev_delay | world_model | 1115 | 16.20 | 0.62 | 95% | -1,023 / -7,977 |
| hvac_curtail | delta_lgbm | 18 | 0.80 | 0.63 | 0% | -0 / 0 |
| hvac_curtail | none (used) | 18 | 0.76 | – | – | 0 / 0 |
| hvac_curtail | world_model | 18 | 2.46 | -0.02 | 6% | 0 / 0 |
| load_shift_33 | delta_lgbm (used) | 2912 | 0.44 | 0.66 | 65% | -251 / -1,041 |
| load_shift_33 | none | 2912 | 0.52 | – | – | 0 / -1,041 |
| load_shift_33 | world_model | 2912 | 1.77 | 0.21 | 45% | 2,579 / -1,041 |
| precool_42 | delta_lgbm (used) | 4992 | 1.04 | 0.97 | 85% | 34,913 / 38,998 |
| precool_42 | none | 4992 | 2.51 | – | – | 0 / 38,998 |
| precool_42 | world_model | 4992 | 2.90 | 0.69 | 62% | 25,086 / 38,998 |
| thermal_preheat | delta_lgbm (used) | 11 | 0.90 | 0.91 | 46% | 0 / 1 |
| thermal_preheat | none | 11 | 1.01 | – | – | 0 / 1 |
| thermal_preheat | world_model | 11 | 2.29 | 0.15 | 9% | -0 / 1 |

## Does forecasting turn into savings? (prosumer batteries, both peak days)

Share of the best possible battery savings (perfect knowledge of the day) captured, same forecasts:

| Planner | Winter | Summer |
|---|---|---|
| Hourly re-planning with a perfect forecast | 99% | 102% |
| Hourly re-planning on one forecast line (before) | 62% | 47% |
| Hourly re-planning over forecast scenarios (now) | 78% | 66% |

### The two measured buildings

| Building | Season | LightGBM % | No weather % | Last week % | World model % |
|---|---|---|---|---|---|
| Boston Public Library Central | shoulder | 4.8 | 4.7 | 7.0 | 6.1 |
| Boston Public Library Central | summer | 5.8 | 6.1 | 7.3 | 7.8 |
| Boston Public Library Central | winter | 5.0 | 4.9 | 6.5 | 8.2 |
| HouseZero (Harvard) | shoulder | 9.6 | 9.7 | 14.1 | 11.8 |
| HouseZero (Harvard) | summer | 9.4 | 10.0 | 14.4 | 9.4 |
| HouseZero (Harvard) | winter | 8.1 | 8.8 | 13.1 | 8.7 |

## Winter peak day: 2026-01-30

Grid-need hours: 9 · heat warning: no · signed receipts: 140 · commands refused by the trust layer: 9 (includes one deliberate oversized test request per hour) · paid out to members: $2,160.36

Coordination round: planned community peak 12,808 → 12,764 kW.

| Strategy | Community peak kW | Avg import in grid-need hours kW | Bills $ | Net of payouts $ |
|---|---|---|---|---|
| No battery | 14,089 | 12,807 | 228,938 | 228,938 |
| Vendor default battery | 13,924 | 12,785 | 227,143 | 227,143 |
| Each battery optimizing alone (hourly re-planning) | 13,067 | 12,114 | 207,470 | 207,470 |
| Collective | 13,215 | 11,848 | 207,671 | 205,511 |
| Perfect foresight, each alone (ceiling) | 12,973 | 12,198 | 201,298 | 201,298 |

Collective vs no battery: grid-need-hour import −7.5%, community peak −6.2%. Collective vs each battery alone: grid-need-hour import −2.2%, community peak +1.1%.

## Summer peak day: 2025-06-24

Grid-need hours: 6 · heat warning: yes · signed receipts: 141 · commands refused by the trust layer: 15 (includes one deliberate oversized test request per hour) · paid out to members: $1,044.64

Coordination round: planned community peak 13,996 → 13,890 kW.

| Strategy | Community peak kW | Avg import in grid-need hours kW | Bills $ | Net of payouts $ |
|---|---|---|---|---|
| No battery | 13,969 | 12,109 | 218,356 | 218,356 |
| Vendor default battery | 13,963 | 12,021 | 216,646 | 216,646 |
| Each battery optimizing alone (hourly re-planning) | 13,833 | 11,518 | 207,090 | 207,090 |
| Collective | 13,733 | 11,476 | 206,835 | 205,790 |
| Perfect foresight, each alone (ceiling) | 13,511 | 11,552 | 201,153 | 201,153 |

Collective vs no battery: grid-need-hour import −5.2%, community peak −1.7%. Collective vs each battery alone: grid-need-hour import −0.4%, community peak -0.7%.

## What if tomorrow is hotter? (summer peak day, plan only)

| Forecast shift | Forecast high °C | Heat warning | Planned peak solo kW | Planned peak coordinated kW | kW assigned in grid-need hours |
|---|---|---|---|---|---|
| -10 °C | 31.2 | no | 12,315 | 12,211 | 7,300 |
| -5 °C | 36.2 | yes | 13,694 | 13,612 | 6,304 |
| +0 °C | 41.2 | yes | 13,996 | 13,890 | 9,263 |
| +3 °C | 44.2 | yes | 14,005 | 13,901 | 9,313 |

With a heat warning, cooling centers (libraries, community centers, BPL Central) hold 50% battery and refuse building modes; fire and police always hold 80%; museums offer battery only.

## Boston projection (BERDO 2025 stock, buildings ≥ 20,000 sq ft, apartments and homes excluded)

| Adoption | Winter MW avoided | Winter $/day | Summer MW avoided | Summer $/day |
|---|---|---|---|---|
| 0% | 0.00 | 0 | 0.00 | 0 |
| 10% | 3.00 | 69,007 | 1.99 | 56,289 |
| 20% | 6.00 | 138,013 | 3.97 | 112,578 |
| 30% | 9.00 | 207,020 | 5.96 | 168,867 |
| 50% | 15.00 | 345,033 | 9.93 | 281,445 |

## Honest caveats
- Measured buildings: HouseZero and BPL Central. Civic, retail and business members are NREL ComStock building designs driven by measured 2025–26 HouseZero weather; homes are synthetic (homesim, seed 42).
- On the single highest hour, the collective is below batteries acting alone in summer and about 1% above in winter: members give up a little of their own peak shaving to deliver in the grid-need hours, where the collective beats every realistic strategy.
- Batteries for civic/business members are hypothetical (2 h at 30% of peak); flex costs and demand-response pay are assumptions labeled in code.
- One tariff (Concord MA G-2) stands in for Eversource G-2; the demand charge is billed on each simulated day's peak. Bills are single peak days, not annualized.
- The HouseZero rooftop sensor reads hotter than the airport on sunny afternoons; it is still the only weather source by the team's data rule.
