# Public baselines for homesim calibration

Downloaded 2026-10-24 into `raw/`. Re-fetch with `uv run homesim-baseline`
(the 46 MB ResStock CSV is gitignored).

| File | Source | Coverage | Used for |
| --- | --- | --- | --- |
| `nationalgrid_meco_load_shapes.xlsx` | National Grid (Massachusetts Electric) supplier load shapes, [MECOLS.xlsx](https://forms.nationalgrid.com/files/loaddata/massachusetts/MECOLS.xlsx), linked from the [MA Electric ESCO page](https://www.nationalgridus.com/energy-service-companies/MA-Electric/Information-and-Forms) | Daily x 24 hourly kW for the average customer by rate class (G-1, G-2, G-3, R-1, S-0), 2023-01-01 to 2026-06-30 | Main calibration target: R-1 hourly shape and daily totals **on the same dates as HouseZero** |
| `eversource_ema_hourly_rate_class_profiles.xlsx` | Eversource [Eastern MA supplier info](https://www.eversource.com/content/nh/about/about-us/doing-business-with-us/energy-supplier-information/electric-massachusetts) | Hourly R1-R4 class profiles, calendar 2023 only | Shape cross-check (different year) |
| `resstock_2024_2_amy2018_ma_single_family_detached_up00.csv` | NREL ResStock 2024.2, AMY 2018, [OEDI data lake](https://data.openei.org/s3_viewer?bucket=oedi-data-lake&prefix=nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2024/resstock_amy2018_release_2/) | 15-min aggregate of ~1.53 M MA single-family detached homes, by end use, 2018 weather | Single-family magnitude (9,287 kWh/yr per home) and end-use split |
| `eia_2024_table_5A_residential_avg_bill.pdf` | EIA [Table 5A, 2024](https://www.eia.gov/electricity/sales_revenue_price/pdf/table_5A.pdf) | Annual 2024 | MA all-household average: 570 kWh/month |

## Caveats
- R-1 covers all residential customers on the regular rate, including apartments and
  some electric-heat homes. Use it for **shape and day-to-day weather response**, not
  single-family magnitude.
- ResStock is itself a simulation (calibrated to measured data) and uses 2018 weather.
  Its timestamps mark the end of each 15-minute interval in local standard time.
- National Grid columns `HR_1..HR_24` are hour-ending; homesim maps `HR_1` to the
  interval starting 00:00.
