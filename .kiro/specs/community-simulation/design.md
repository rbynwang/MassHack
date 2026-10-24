# Design: Boston Community Simulation

## Loop (one simulated day, hourly)
```
for hour in day:
    fc   = {m: world_model.forecast(m, history, weather_fc) for m in members}   # 1 forecast
    own  = {m: battery_optimizer(m, fc[m], tariff) for m in prosumers}          # 2 own plan
    offs = {m: flex_offer(m, own.get(m), fc[m], hour) for m in members}         # 3 offers
    if grid_need(hour):
        plan = coordinator.assign(offs, target_kw)                              # 4 decide
        plan = coordinator.check_with_world_model(plan, fc)                     #   reject new peaks
    for cmd in plan: trust.execute_or_block(cmd, limits[cmd.member])            # 5 act
    receipts += trust.sign(delivered)                                           # 6 receipts
settle(receipts)                                                                # split revenue
```

## Modules (folder `community/`)
- `members.py`: load members and limits; `Member` dataclass (id, type, source, pv_kwdc, battery_kwh, battery_kw, modes, limits).
- `offers.py`: flexibility from battery headroom (state of charge vs own plan) and from building modes (`load_shift_33 - baseline`, `precool_42 - baseline`, `thermal_preheat - baseline`, `hvac_curtail - baseline`, including rebound); cost = lost savings + comfort penalty.
- `coordinator.py`: target kW for a grid-need hour (for example 15% of community load); merit-order assignment; world-model check for new peaks.
- `trust.py`: limits check (blocks in code), Ed25519 signing and verification (`cryptography` or `pynacl`), JSON receipts in `results/receipts/`.
- `settlement.py`: pro-rata split; per-member statement.
- `boston.py`: scale per-archetype results by zip from `boston_stock.csv`; adoption scenarios; export `app/public/boston.json`.
- `run_day.py`: CLI `python -m community.run_day --date 2026-01-xx --adoption 0.2`.

## Day selection (2025–26 only)
- Winter: the day with the highest ISO-NE morning system load in Dec 2025–Feb 2026.
- Summer: the day with the highest ISO-NE afternoon system load in Jun–Aug 2025.

## Outputs
`results/community_<date>.json` (per hour: forecasts, offers, assignments, refused commands, receipts), `results/settlement_<date>.json`, `app/public/community.json`, `app/public/boston.json`.

## Honesty labels
Every exported number carries `source`: measured (HouseZero, ISO-NE, BERDO), simulated_template_hz_weather (the 40 business members), projected (Boston scaling), synthetic (event days, battery sizes, flex costs).
