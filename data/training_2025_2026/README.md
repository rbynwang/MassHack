# Training data, June 2025 – May 2026

The exact tables the forecasting / world-model run was trained and evaluated on. Every time series covers
**2025-06-01 00:00 to 2026-06-01 00:00 America/New_York**, on a 15-minute UTC grid (interval start). Read them with
`load_dataset.py`.

## Files

| File | Contents | Kind |
|---|---|---|
| `weather.parquet` | HouseZero weather station: outdoor temperature (short gaps filled, flagged), humidity (sparse), wind, solar radiation, solar zenith, `pv_per_kwdc` (kW of solar per kW of panels, from measured radiation) | Measured |
| `grid.parquet` | ISO-NE real-time hourly price at .Z.NEMASSBOST ($/MWh, forward-filled to 15 min), ISO-NE system load (MW), flags `grid_stress`, `price_spike`, `dr_event_summer`, `dr_event_winter` | Measured; event flags synthetic |
| `dr_events_2025.csv` | ConnectedSolutions-style event calendar: 40 summer weekdays 15:00–18:00, 10 winter mornings 07:00–09:00, picked from real ISO-NE peak load | Synthetic |
| `members.csv` | 41 members: `hz_main` (HouseZero) + 40 Boston building designs (8 each: small office, medium office, standalone retail, strip mall, full-service restaurant); size, zip, solar kW, hypothetical battery, available modes | Mixed |
| `members_load_2025_2026.parquet` | One row per member, mode and 15 minutes: `demand_kw`, `pv_kw`, `hvac_kw`, `cooling_kw`, `heating_kw`, `source`. Modes: `baseline`, `load_shift_33`, `precool_42` (business members), `thermal_preheat`, `hvac_curtail` (HouseZero) | Measured (HouseZero) / simulated |
| `housezero_15min_aligned.parquet` | All HouseZero 2025–26 channels aligned at 15 min in SI units (electricity by circuit, solar, indoor temperature/CO2/humidity, windows, valves, radiant-slab and geothermal energy) | Measured |
| `boston_stock.csv`, `berdo_buildings_clean.csv`, `berdo_archetype_medians.csv` | City of Boston BERDO 2026 disclosure (2025 data): buildings ≥ 20,000 sq ft by zip and type, 2025 electricity; owner names removed | Reported |
| `template_fit_metrics.csv` | How well each building design's weather response was learned (held-out R², MAE %) | QA |
| `tariff.json` | Example Massachusetts G-2 rate (Town of Concord, effective 2026-04-01) and an Eversource placeholder to verify | Real rate |
| `build_scripts/` | The scripts that produced these files (set `MASSHACK_WORK` to a working folder with the raw downloads) | Code |

## How the 40 business members were made

NREL ComStock 2025 Release 3 Boston (Suffolk County) building designs were used only as physics templates. For each design
and mode, a gradient-boosted model learned how its electricity responds to temperature, solar radiation and the calendar,
then predicted 2025–26 demand from HouseZero's measured 2025–26 weather. No pre-2025 timestamps, weather or loads are in
these files. Held-out fit: R² 0.94–0.98, typical error 5–8%. Pre-cool (`precool_42`) raises the midday peak in this data.

## Known limits

- Only HouseZero (and the weather and grid data) are measured. Business members are simulated.
- Batteries and demand-response events are assumptions, labeled in `members.csv` and `dr_events_2025.csv`.
- The period starts 2025-06-01. May 2025 is not included yet.
- The civic members (schools, libraries, fire and police stations, museums, courthouses, community centers), the large
  retail members and the synthetic homes were prepared later and are not part of this training run.

## Sources and attribution

- HouseZero one year dataset (June 2025 – May 2026), Harvard Center for Green Buildings and Cities, DOI 10.6084/m9.figshare.32790984.v1, CC BY 4.0. Transformed derivative; not an official Harvard release.
- NREL ComStock 2025 Release 3, Open Energy Data Initiative (building designs used as templates).
- ISO New England real-time LMP and system load, retrieved with the gridstatus Python package.
- City of Boston BERDO 2026 data disclosure (published 2026-09-30), Analyze Boston.
- OpenEI Utility Rate Database: Town of Concord MA G-2.
