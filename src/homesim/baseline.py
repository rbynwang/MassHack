"""Public historical baselines used to calibrate and sanity-check homesim.

Sources (see data/baseline/README.md):
- National Grid (Massachusetts Electric) R-1 class load shape, hourly, 2023-01 to 2026-06.
- Eversource Eastern MA hourly rate class profiles (R1-R4), calendar 2023.
- NREL ResStock 2024.2 (AMY 2018), MA single-family detached aggregate, 15-min.
- EIA 2024 Table 5A: average monthly residential consumption by state.

Usage:
    uv run homesim-baseline            # download raw files (skips existing)
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

SOURCES = {
    "nationalgrid_meco_load_shapes.xlsx": "https://forms.nationalgrid.com/files/loaddata/massachusetts/MECOLS.xlsx",
    "eversource_ema_hourly_rate_class_profiles.xlsx": "https://www.eversource.com/docs/default-source/doing-business/ema-hourly-rate-class-profiles.xlsx",
    "resstock_2024_2_amy2018_ma_single_family_detached_up00.csv": (
        "https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/"
        "2024/resstock_amy2018_release_2/timeseries_aggregates/by_state/upgrade%3D0/state%3DMA/up00-ma-single-family_detached.csv"
    ),
    "eia_2024_table_5A_residential_avg_bill.pdf": "https://www.eia.gov/electricity/sales_revenue_price/pdf/table_5A.pdf",
}

# EIA 2024 Table 5A, Massachusetts residential: average monthly consumption (kWh).
EIA_MA_2024_AVG_MONTHLY_KWH = 570


def raw_dir(root: Path) -> Path:
    return root / "data" / "baseline" / "raw"


def fetch(root: Path) -> None:
    d = raw_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        out = d / name
        if out.exists():
            print(f"exists  {out}")
            continue
        print(f"fetch   {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(out, "wb") as fh:
            fh.write(r.read())


def national_grid_r1(root: Path, start: str, end: str) -> pd.DataFrame:
    """R-1 average-customer kW by local date x hour-of-day (0..23 = interval start)."""
    ng = pd.read_excel(raw_dir(root) / "nationalgrid_meco_load_shapes.xlsx", sheet_name="MECO ALL")
    ng = ng[ng["Rate"].astype(str).str.strip() == "R-1"].copy()
    ng["Date"] = pd.to_datetime(ng["Date"])
    ng = ng.set_index("Date").drop(columns="Rate").loc[start:end]
    ng.columns = list(range(24))  # HR_1 (hour ending 01:00) -> interval starting 00:00
    return ng.astype(float)


def resstock_sfd_per_home(root: Path) -> dict:
    """Per-home annual and monthly electricity for MA single-family detached (2018 weather)."""
    f = raw_dir(root) / "resstock_2024_2_amy2018_ma_single_family_detached_up00.csv"
    cols = ["timestamp", "units_represented", "out.electricity.total.energy_consumption.kwh"]
    rs = pd.read_csv(f, usecols=cols, parse_dates=["timestamp"])
    units = float(rs["units_represented"].iloc[0])
    # ResStock timestamps mark the end of each 15-min interval.
    kwh = rs.set_index(rs["timestamp"] - pd.Timedelta(minutes=15))["out.electricity.total.energy_consumption.kwh"] / units
    monthly = kwh.resample("MS").sum()
    hourly_kw = kwh.resample("h").sum()
    shape = hourly_kw.groupby(hourly_kw.index.hour).mean()
    return {
        "annual_kwh": float(kwh.sum()),
        "monthly_kwh": monthly,
        "hour_shape": shape / shape.mean(),
    }


def housezero_heat_pump_response(root: Path, bins: np.ndarray) -> pd.Series:
    """Mean HouseZero heat-pump electricity by outdoor-temperature bin (ground-source unit)."""
    e = pd.read_csv(root / "data/housezero/energy_hourly.csv", usecols=["timestamp_utc", "Heat_pump (kW)"])
    h = pd.read_csv(root / "data/housezero/housezero_hourly.csv", usecols=["timestamp_utc", "outdoor_temperature_c"])
    df = e.merge(h, on="timestamp_utc").dropna()
    cats = pd.cut(df["outdoor_temperature_c"], bins)
    return df.groupby(cats, observed=False)["Heat_pump (kW)"].mean()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public baseline data for homesim.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    fetch(args.root)


if __name__ == "__main__":
    main()
