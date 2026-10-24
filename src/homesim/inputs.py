"""Shared hourly inputs: HouseZero weather and PV, gap-filled, plus calendar features.

The simulator needs a continuous outdoor temperature series, so measured gaps are
filled here. Every filled hour is flagged; the filled values are inputs to the
simulation, not measurements.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class Inputs:
    frame: pd.DataFrame          # one row per hour, UTC index
    pv_per_kw_dc: np.ndarray     # HouseZero PV normalised by its nameplate (kW/kW_dc)
    temp_out_c: np.ndarray
    solar_w_m2: np.ndarray
    local_hour: np.ndarray       # float hour of day in local time (interval start)
    day_index: np.ndarray        # 0..n_days-1, local calendar day
    is_workday: np.ndarray       # bool per hour (Mon-Fri and not a MA holiday)
    day_is_workday: np.ndarray   # bool per local day
    day_dates: pd.DatetimeIndex  # local dates
    n_hours: int
    n_days: int


def _fill_series(s: pd.Series, max_gap_h: int, window_days: int) -> tuple[pd.Series, pd.Series]:
    """Interpolate short gaps; fill long gaps with a same-hour climatology."""
    missing = s.isna()
    interp = s.interpolate(method="time", limit=max_gap_h, limit_area="inside")
    # Same hour-of-day mean over a centred window of days.
    by_hour = s.groupby(s.index.hour)
    clim = by_hour.transform(
        lambda x: x.rolling(2 * window_days + 1, center=True, min_periods=3).mean()
    )
    filled = interp.fillna(clim)
    # Anything still missing (edges): fall back to the overall same-hour mean.
    filled = filled.fillna(by_hour.transform("mean"))
    return filled, missing


def load_inputs(cfg: dict, root: Path) -> Inputs:
    icfg = cfg["inputs"]
    cols = icfg["columns"]
    path = root / icfg["housezero_hourly_csv"]
    raw = pd.read_csv(path, usecols=list(cols.values()))
    raw[cols["timestamp"]] = pd.to_datetime(raw[cols["timestamp"]], utc=True)
    raw = raw.set_index(cols["timestamp"]).sort_index()

    max_gap = int(icfg["max_interp_gap_h"])
    win = int(icfg["climatology_window_days"])

    temp, temp_missing = _fill_series(raw[cols["temp_out_c"]], max_gap, win)

    solar_raw = raw[cols["solar_w_m2"]].clip(lower=0.0)
    solar, solar_missing = _fill_series(solar_raw, max_gap, win)

    # PV: clip negative night noise (allowed in features only, source untouched).
    pv_raw = raw[cols["pv_kw"]].clip(lower=0.0)
    pv_missing = pv_raw.isna()
    # Fill PV gaps from irradiance with a through-origin fit on complete hours.
    ok = pv_raw.notna() & solar_raw.notna() & (solar_raw > 50)
    k = float((pv_raw[ok] * solar_raw[ok]).sum() / (solar_raw[ok] ** 2).sum())
    pv = pv_raw.fillna(solar * k).clip(lower=0.0)

    pv_per_kw_dc = (pv / float(icfg["housezero_pv_capacity_kw_dc"])).to_numpy()

    tz = cfg["period"]["timezone"]
    local = raw.index.tz_convert(tz)
    local_hour = (local.hour + local.minute / 60.0).to_numpy(dtype=float)
    local_dates = local.normalize().tz_localize(None)
    day_dates = pd.DatetimeIndex(sorted(local_dates.unique()))
    day_lookup = {d: i for i, d in enumerate(day_dates)}
    day_index = np.array([day_lookup[d] for d in local_dates], dtype=np.int32)

    holidays = set(pd.to_datetime(cfg.get("holidays", [])))
    day_is_workday = np.array(
        [(d.dayofweek < 5) and (d not in holidays) for d in day_dates], dtype=bool
    )

    frame = pd.DataFrame(
        {
            "timestamp_local": local,
            "temp_out_c": temp.to_numpy(),
            "solar_w_m2": solar.to_numpy(),
            "pv_per_kw_dc": pv_per_kw_dc,
            "temp_filled": temp_missing.to_numpy(),
            "solar_filled": solar_missing.to_numpy(),
            "pv_filled": pv_missing.to_numpy(),
        },
        index=raw.index,
    )
    frame.index.name = "timestamp_utc"

    return Inputs(
        frame=frame,
        pv_per_kw_dc=pv_per_kw_dc,
        temp_out_c=temp.to_numpy(dtype=float),
        solar_w_m2=solar.to_numpy(dtype=float),
        local_hour=local_hour,
        day_index=day_index,
        is_workday=day_is_workday[day_index],
        day_is_workday=day_is_workday,
        day_dates=day_dates,
        n_hours=len(raw),
        n_days=len(day_dates),
    )
