# homesim dataset card — 0.1.0-dev-balanced-200

**Synthetic data. Only weather and PV inputs are measured (HouseZero).**

- homesim version: 0.1.0; config version: 0.1.0-dev; seed: 42
- Mode: balanced; homes: 200; hours per home: 9,504 (2025-05-01 to 2026-05-31 local)
- Generated in 3 s. Build order steps 1-2 of the guideline (simulator + population + calibration).

## Inputs
- HouseZero hourly outdoor temperature, solar radiation and PV (Harvard CGBC, CC BY 4.0;
  DOIs 10.6084/m9.figshare.30260233.v1 and 10.6084/m9.figshare.32790984.v1).
- Gaps in inputs are filled (short gaps interpolated, long gaps from a same-hour climatology,
  PV gaps from irradiance). Filled hours are flagged in `weather_inputs.parquet`.
- PV is HouseZero PV / 15 kW nameplate x home kW_dc x (derate / 0.875) x (1 + per-home noise).

## Files
- `homes.parquet`: one row per home (guideline columns plus `capacitance_kwh_per_c`,
  `cooling_capacity_kw`, `pv_noise_frac`, `has_electric_water_heater`, `internal_gain_occupied_kw`,
  `window_aperture_m2`, `furnace_blower_kw`, `window_ac_fraction`).
- `hourly/`: Parquet partitioned by `home_type` and `month` (local). Power in kW (hourly mean).
  `base_kw` = all non-HVAC, non-EV household load. `heat_pump_kw` covers heat-pump heating and cooling.
  `blower_kw` = gas furnace blower (not in the guideline schema). `grid_export_kw` is a positive magnitude.
  Battery is not dispatched.
- `weather_inputs.parquet`, `config.yaml` (resolved), `calibration.json`, `home_<id>_weeks.png`.
- Not generated yet (guideline steps 3-5, section 7): flex_down_kw, flex_up_kw, flex_duration_h, event_id, responded, delivered_kw, actual_load_kw, counterfactual_load_kw, oracle_battery_kw, is_missing, is_anomaly; `events.parquet`.

## Splits
Home split stored in `homes.split` ({'train': 0.7, 'val': 0.15, 'test': 0.15}). Apply the time split on top:
train homes ['2025-05', '2026-01'], val homes ['2026-02', '2026-03'],
test homes ['2026-04', '2026-05'] (inclusive months).

## Home types
```
home_type
hp_nopv_nobat_ev0       17
gasca_nopv_nobat_ev1    14
gaswa_nopv_nobat_ev0    14
gasca_nopv_nobat_ev0    13
hp_nopv_nobat_ev1       12
hp_pv_bat_ev1            9
gasca_pv_bat_ev1         9
gaswa_nopv_nobat_ev2     8
gaswa_pv_nobat_ev0       8
hp_pv_bat_ev0            8
gaswa_pv_nobat_ev2       7
gasca_nopv_nobat_ev2     7
gaswa_pv_bat_ev1         6
hp_pv_nobat_ev1          6
gasca_pv_bat_ev0         6
gaswa_nopv_nobat_ev1     5
gaswa_pv_nobat_ev1       5
hp_pv_nobat_ev0          5
gasca_pv_nobat_ev0       5
hp_nopv_bat_ev1          5
gaswa_pv_bat_ev0         5
gasca_pv_bat_ev2         4
gasca_pv_nobat_ev1       4
hp_pv_nobat_ev2          3
gaswa_pv_bat_ev2         3
hp_pv_bat_ev2            3
gasca_nopv_bat_ev0       2
gasca_pv_nobat_ev2       2
hp_nopv_nobat_ev2        2
gaswa_nopv_bat_ev2       1
gaswa_nopv_bat_ev1       1
gaswa_nopv_bat_ev0       1
```

## Calibration
```
Calibration checks (guideline section 5)
--------------------------------------------
1. Shape vs National Grid R-1 (non-HP homes): r(all)=0.797, r(Jan-Feb)=0.752, r(Jul-Aug)=0.766; daily kWh r=0.808, sim/R-1 level=1.752
2. Monthly use: sim 1175.5 kWh/mo (by heating {'gas_furnace': 970.3, 'heat_pump': 1556.7}); EIA MA all households 570; R-1 same dates 553.9; ResStock MA SFD 773.9 -> above EIA: True
3. HP homes top 95 hours: 78% in Jan-Feb, 81% at 5-10 AM, 62% both; peak 11.22 kW at 2026-01-24 07:00:00-05:00
4. Solar homes net-exporting 11-14h Apr-Aug: 100% of 98 (median net -2.419 kW)
5. HP load vs outdoor temp, shape r vs HouseZero = 0.949 (GSHP reference)
```
Full values: `calibration.json`. Baselines: National Grid R-1 load shape (same dates), EIA 2024 Table 5A,
NREL ResStock 2024.2 MA single-family detached (2018 weather). See `data/baseline/README.md`.
