---
inclusion: fileMatch
fileMatchPattern: ["src/**/*.py", "scripts/**/*.py", "notebooks/**", "data/**"]
---

# HouseZero data rules

Source: `data/housezero/` (Harvard CGBC HouseZero, May 2025 – May 2026, CC BY 4.0).
Start with `housezero_hourly.csv`. All timestamps are UTC, interval start.

- `grid_net_kw` is signed net grid exchange, **not** building demand. Exports
  are negative. Do not sum all electrical columns: PV and grid meters overlap.
- Building demand ≈ grid net + PV, but check meter balance before relying on it.
- `pv_total_raw_kw` keeps negative night-time noise; clip only in features, never in the source.
- `Battery_cabinet (kW)` is a circuit reading, **not** state of charge. Battery,
  tariff and savings are modeled by us, not measured.
- Hourly values are blank unless the hour is complete; check the `*_valid_minutes`
  columns. Humidity is ~80% missing — do not rely on it.
- `rain_fraction` is the fraction of minutes raining, not millimetres.
- Backtests must never use future weather or load as if known; use a
  forecast proxy (e.g. persistence or noised actuals) and say so.
- Credit Harvard CGBC and cite both dataset DOIs in the demo and README.
