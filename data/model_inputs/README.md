# data/model_inputs: what the model trains on

Every series covers **2025-05-01 00:00 to 2026-06-01 00:00 America/New_York** (stored in UTC, interval start). Load with `masshack.data.Dataset("data/model_inputs")`, which resamples to hourly, or with the small `load_dataset.py` helper in this folder.

| File | Rows | What it is |
|---|---|---|
| `members.csv` | 316 | One row per building. 116 are in the community (`in_community=True`); 200 are training-only homes. |
| `members_load_2025_2026.parquet` | 8.2 M | Long table of load per member × mode (15-min; synthetic homes hourly). |
| `weather.parquet` | 38,016 | HouseZero measured weather, 15-min. The only weather source. |
| `grid.parquet` | 38,016 | ISO-NE real-time LMP (.Z.NEMASSBOST) and system load, 15-min, with stress / spike / DR flags. |
| `tariff.json` | – | `ma_g2_example`: Town of Concord MA G-2 (OpenEI URDB), the commercial tariff used. |
| `dr_events_2025.csv` | 50 | Synthetic ConnectedSolutions-style DR days, chosen from real ISO-NE peak load (`synthetic=True`). |
| `boston_stock_civic.csv` | 157 | BERDO 2025 floor area and kWh by zip × archetype, for the Boston projection. |
| `boston_stock.csv`, `berdo_archetype_medians.csv` | – | Earlier BERDO aggregates (kept for reference). |
| `civic_members.csv` | 34 | Build sheet for the civic and large-retail members (template, BERDO type, sizing). |
| `template_fit_metrics.csv`, `civic_template_fit_metrics.csv` | – | Held-out fit quality of each ComStock template's weather-response model (R², error). |
| `mode_fix_report.csv` | 76 | Per building × action: true paired effect, new effect, and the old (noisy) difference. See `EVALUATION.md` §3. |
| `load_dataset.py` | – | Helper: `load_weather()`, `load_grid()`, `load_members()`, `load_member_loads(member_id, mode)`. |

## members.csv: important columns
| Column | Meaning |
|---|---|
| `member_id` | `hz_main` (HouseZero), `bpl_central` (BPL Central), `school_1` … (civic), `cs_<bldg>` (small business), `home_H…` (community homes), `home_H…_t` (training-only homes). |
| `group` | `housezero`, `civic_measured`, `civic`, `large_retail`, `small_business`, `home`. |
| `role` | `prosumer` (has solar + battery, offers battery flex) or `flex` (offers building modes / EV delay only). |
| `source` | `measured`, `simulated_template_hz_weather` (ComStock design driven by HouseZero weather), or `synthetic_homesim`. |
| `battery_kwh`, `battery_kw`, `battery_label` | Battery size. "HYPOTHETICAL" = 2 h at 30% of peak. |
| `pv_kwdc` | Solar size (kWdc). PV output = `pv_per_kwdc` (weather file) × `pv_kwdc`. |
| `min_soc`, `cooling_center`, `allow_building_modes` | Member rules that become trust-layer limits (cooling centers keep 50% under a heat warning; fire and police 80%). |
| `has_modes` | Actions this building can take, `|`-separated. |
| `tariff_id` | `ma_g2_example` (commercial) or `residential_flat`. |
| `in_community` | False = used only to train the world model. |

## members_load_2025_2026.parquet: columns
`timestamp_utc, member_id, mode, demand_kw, pv_kw, hvac_kw, cooling_kw, heating_kw, source`

| Mode | Members | What it is |
|---|---|---|
| `baseline` | all 316 | The building as it runs. |
| `load_shift_33` | 28 offices, schools, libraries, courthouses | ComStock measure 33. Since `fix_modes`: baseline + paired effect (about +3–4% early morning, −1–2% midday to evening). |
| `precool_42` | 48 | ComStock measure 42: raises load at 11 am – 2 pm and lowers it after. **Raises the midday peak; never offered as peak reduction.** |
| `ev_delay` | 11 homes with EVs | EV charging moved 6 h later. Same energy, later. |
| `thermal_preheat`, `hvac_curtail` | HouseZero | Rule-based flex on measured HouseZero data (differs from baseline only on ~150 hours). |

## weather.parquet (HouseZero station)
`outdoor_temp_c` (rooftop sensor; reads ~1.5 °C above Logan on hot afternoons), `rh_pct`, `wind_m_s`, `ghi_w_m2`, `rain_frac`, `solar_zenith_deg`, `pv_per_kwdc`, plus `*_missing` / `temp_fill_flag` gap flags and calendar columns.

## grid.parquet (ISO-NE)
`system_load_mw`, `lmp_usd_mwh` (+ energy / congestion / loss parts), `grid_stress`, `price_spike`, `dr_event_summer`, `dr_event_winter`, plus calendar columns.

## Sources and licenses
- HouseZero: © Harvard CGBC, CC BY 4.0 (DOI 10.6084/m9.figshare.32790984.v1; May 2025 from the earlier release).
- BPL Central: City of Boston / Analyze Boston, PDDL.
- ComStock 2025 R3: NREL (physics templates only).
- BERDO 2026 disclosure (2025 data): City of Boston.
- ISO-NE data via gridstatus.
- Homes: the team's homesim generator, seed 42.
