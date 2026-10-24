# Boston Public Library — Central Library electricity data

**Building:** Central Library, 700 Boylston Street, Boston, Massachusetts.
**Source:** City of Boston, Analyze Boston, Central Library Electricity Usage.
**Requested selection:** May 1, 2025 through May 31, 2026, inclusive, in Eastern time.
**Original measurement:** Electric power load in kW, recorded every five minutes.

## Start here

- `bpl_5min_original.csv`: the 85,244 original observations found in the requested period, with original columns, Eastern-time strings and numeric values preserved.
- `bpl_hourly.csv`: a regular UTC hourly grid for joining to HouseZero; inspect `quality_flag` before use.
- `bpl_5min_utc.csv`: a regular five-minute UTC grid; missing/unresolved readings remain blank.
- `coverage_by_month.csv`: actual and expected sample counts and hourly completeness by local month.
- `data_quality.json`: coverage, timestamp and value checks.
- `sources.json`: source, license, retrieval time and original snapshot checksum.
- `ambiguous_local_time_original.csv`, when present: original records from the repeated daylight-saving hour that cannot be assigned to a unique UTC instant.

Copy `data/boston_public_library/` into the MassHack repository.

## Coverage limitation

The requested period is **not fully observed**. The first source start timestamp in the selection is **2025-05-01 00:00:00**, and the last is **2026-05-28 00:05:00**, Eastern time. There are gaps throughout the period; May 2026 contains only 905 original five-minute observations. A regular exported timestamp grid does not mean all its intervals contain measurements. No missing readings are replaced with zero or extrapolated.

For dispatch backtests, choose contiguous intervals with sufficient coverage, and compare every strategy on the same observations. Do not join observations across missing days as if they were adjacent. Do not calculate a full-month bill or demand charge from incomplete observations without explicitly modeling and disclosing the missing data.

## Hourly fields

| Field | Meaning |
| --- | --- |
| timestamp_utc | Start of the hourly interval, UTC |
| timestamp_eastern | Same instant in America/New_York, including UTC offset |
| mean_kw_available | Arithmetic mean of available valid five-minute power readings; partial hours are explicitly flagged |
| estimated_energy_kwh_complete_hour | One-hour mean kW multiplied by one hour, using twelve valid five-minute readings; blank for incomplete or ambiguous hours. This is derived energy, not a utility-billed measurement. |
| observed_5min_intervals | Count of usable observations in the hour |
| expected_5min_intervals | 12 |
| quality_flag | complete, partial, missing, or ambiguous_local_time |

## Timezone handling

The source headers specify Eastern time but the original strings have no UTC offsets. Unambiguous local times are converted with America/New_York timezone rules. During the repeated hour at the end of daylight saving time, the actual occurrence cannot be inferred from the original strings. Such records are retained separately; both possible UTC hours are flagged, rather than inventing an offset. The original CSV remains the authoritative export of observed values.

## Scope

This is a **large public/community building**, not a small business or individual household. This source contains electricity demand only. It does **not** provide measured solar PV generation, battery operations, weather or electricity tariffs. Any added PV, storage, flexible-load behavior or earnings must be labeled as modeling assumptions or simulation.

## Source and attribution

Official dataset: https://data.boston.gov/dataset/central-library-electricity-usage

Provider: City of Boston / Analyze Boston. Source license: **Open Data Commons Public Domain Dedication and License (PDDL)**, as stated in the official dataset metadata. https://opendatacommons.org/licenses/pddl/

This package is a selected and transformed derivative. It is not an official City of Boston publication or endorsement. Original rows are filtered to the requested period; timezone-normalized grids and hourly summaries are derived outputs. See `sources.json` for exact provenance.
