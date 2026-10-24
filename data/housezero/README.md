# Harvard HouseZero: May 2025 through May 2026

Measured building electricity, photovoltaic output and local weather from HouseZero, Harvard Center for Green Buildings and Cities, Cambridge, Massachusetts, USA.

## Start here

Use `housezero_hourly.csv` for a quick forecasting and battery-dispatch demo. Copy this `data/housezero/` directory into the MassHack repository. The selected period is **2025-05-01 through 2026-05-31 inclusive in America/New_York: 13 calendar months**, comprising 9,504 hours and 570,240 minutes. All exported timestamps are UTC and identify the start of the interval.

| File | Contents |
| --- | --- |
| housezero_hourly.csv | Electricity, PV and weather joined on UTC hour; temperature converted to Celsius; valid-minute counts for key signals |
| energy_hourly.csv | All electrical channels from the source Load.csv, averaged by hour |
| weather_hourly.csv | Weather channels by hour; source temperature units remain Fahrenheit |
| weather_hourly_counts.csv | Number of finite minute observations underlying each hourly weather channel |
| radiation_hourly.csv | Measured solar irradiance by hour, W/m² |
| energy_minute.csv.gz | Source minute values for two PV meters, net exchange, import and signed export |
| weather_minute.csv.gz | Source minute weather values, including temperature, wind, rain status and humidity |
| radiation_minute.csv.gz | Source minute measured solar irradiance |
| data_quality.json | Missing values and incomplete hours for every source channel |
| sources.json | Official source URLs, versions, checksums and selection details |
| Data_Report_2025-2026.pdf | Latest official data dictionary and quality report |

Pandas can open `.csv.gz` files directly. Every individual file in this package is below GitHub's normal 100 MiB file limit; keep minute files compressed when committing.

## Sources and attribution

The selected period combines **May 2025** from the older release and **June 2025–May 2026** from the newer release:

- HouseZero® one year dataset (June 2024 - May 2025), version 1: https://doi.org/10.6084/m9.figshare.30260233.v1
- HouseZero® one year dataset (June 2025 - May 2026), version 1: https://doi.org/10.6084/m9.figshare.32790984.v1
- Official overview: https://harvardcgbc.org/house-zero-data/

Creators and exact file metadata are recorded in `sources.json`. Both datasets are licensed **CC BY 4.0**: https://creativecommons.org/licenses/by/4.0/. Credit Harvard CGBC and cite both dataset DOIs when redistributing or presenting results. This package is a selected and transformed derivative, not an official Harvard release or endorsement.

## Transformations

Minute numeric values are preserved as supplied by the official processed datasets; timestamps are converted to UTC and sorted. No additional interpolation, imputation, clipping or synthetic observations are introduced. The source energy file interleaves the repeated hour at the November daylight-saving transition; the exports are ordered by UTC timestamp to handle this correctly.

Column names are harmonized across releases: `In` becomes `In (kW)`, `Out` becomes `Out (kW)`, and `Gund_RH` becomes `Relative_humidity (%)`. The minute energy file retains only the five main electricity/PV channels, while the hourly energy file retains all electrical channels.

Hourly power, irradiance, temperature, wind speed and humidity are arithmetic means of minute observations. Wind direction uses a circular mean. Rain is the fraction of valid minute rain indicators; it is not precipitation in millimeters. Electrical and irradiance hourly channels are left blank unless all 60 minute observations are finite. Weather hourly channels average available finite observations and remain blank if no observations exist; check weather_hourly_counts.csv and the joined valid-minute columns before modeling. No missing minutes are synthesized. Humidity has particularly sparse source coverage (about 80% of minute entries are blank), so do not assume its hourly estimates have the same coverage as temperature. The quality report distinguishes incomplete hours from measured zeros. All expected timestamps exist; individual sensor values can still be missing.

In the joined hourly file, `pv_total_raw_kw` is the sum of the two measured PV channels. Negative nighttime readings and negative irradiance remain unchanged, including sensor noise and standby readings. Temperature in Celsius is derived as `(F - 32) × 5 / 9`.

## Meter interpretation for the demo

`grid_net_kw` is signed net grid exchange, **not gross building demand**. `grid_import_kw` and `grid_export_signed_kw` retain the source signs; exports are negative. Verify meter balance and consult the official report before reconstructing building demand from net exchange and PV. Do not sum all electrical columns indiscriminately: PV and grid meters overlap with building demand.

All power fields are kW. For a complete one-hour interval, average kW multiplied by one hour gives kWh. Keep energy and power units distinct. `Battery_cabinet (kW)` is an electrical circuit reading, not a battery state-of-charge series. Battery dispatch, utility tariffs, installation costs and savings are not measured by this dataset and must be modeled separately.

Weather comes from the Harvard measurement network accompanying these releases, rather than a weather forecast or synthetic weather model. Refer to the official report for individual sensor locations. In forecast backtesting, future measured weather and future electricity/PV values must not be used as if they were known in advance.
