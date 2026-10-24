---
inclusion: always
---
# Repository structure

```
data/                 2025–26 data layer (read only through data/load_dataset.py)
masshack/             the system, one module per layer
  physics.py          battery + tariff + bill (exact, never learned)
  optimizer.py        each member's battery plan (linear program) and the vendor-default baseline
  world_model.py      JEPA-style world model shared by all members (encoder, predictor, quantile heads, member embedding)
  forecast.py         LightGBM quantile and seasonal-naive forecasters (comparison and fallback)
  agents.py           member agents: forecast -> own plan -> hourly flex offers with cost (prosumers and flex members)
  coordinator.py      grid signals (soak up / use less), merit-order assignment with rebound check, revenue split
  trust.py            member limits enforced in code, Ed25519 signed receipts, hash-chained log
  simulate.py         one day of the collective, realized with actual data, scored against 5 strategies
  boston.py           projection across Boston zips from the BERDO stock
  data.py             loads and resamples the data layer; day-ahead weather forecast without leakage
run_all.py            end-to-end pipeline -> app/public/demo.json
app/public/           demo page (index.html reads demo.json); serve with `python -m http.server -d app/public`
tests/                pytest: physics, trust + coordinator, data period
.kiro/                steering, specs, hooks
```

- Layers only talk downward through plain data (offers, commands, receipts); the trust layer sits between the coordinator and every member.
- Timestamps are tz-aware; simulation runs hourly in America/New_York.
