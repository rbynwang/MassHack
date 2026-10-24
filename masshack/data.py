"""Load the unified 2025-26 data layer and shape it for the agents (hourly by default)."""
from __future__ import annotations

from pathlib import Path
import importlib.util

import numpy as np
import pandas as pd

TZ = "America/New_York"
PERIOD = (pd.Timestamp("2025-05-01", tz=TZ), pd.Timestamp("2026-06-01", tz=TZ))


def _loader(data_dir: Path):
    spec = importlib.util.spec_from_file_location("load_dataset", Path(data_dir) / "load_dataset.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Dataset:
    """All tables, resampled to `freq` (hourly mean kW by default), indexed by local time."""

    def __init__(self, data_dir: str | Path, freq: str = "1h"):
        self.dir = Path(data_dir)
        ld = _loader(self.dir)
        self.freq = freq
        self.dt = pd.Timedelta(freq).total_seconds() / 3600
        w = ld.load_weather()
        g = ld.load_grid()
        self.members = ld.load_members()
        loads = ld.load_member_loads()
        self.stock = ld.load_stock()
        try:
            self.dr_events = ld.load_dr_events()
        except Exception:
            self.dr_events = None

        num_w = ["outdoor_temp_c", "ghi_w_m2", "wind_m_s", "pv_per_kwdc"]
        self.weather = w[num_w].resample(freq).mean().tz_convert(TZ)
        gg = g[["system_load_mw", "lmp_usd_mwh"]].resample(freq).mean()
        flags = g[[c for c in ["grid_stress", "price_spike", "dr_event_summer", "dr_event_winter"] if c in g]].astype(float).resample(freq).max()
        self.grid = pd.concat([gg, flags], axis=1).tz_convert(TZ)
        self.grid["lmp_usd_mwh"] = self.grid["lmp_usd_mwh"].interpolate(limit=6).bfill().ffill()
        self.grid["dr_event"] = self.grid[[c for c in ["dr_event_summer", "dr_event_winter"] if c in self.grid]].max(axis=1).fillna(0) > 0

        cols = [c for c in ["demand_kw", "pv_kw", "cooling_kw", "heating_kw"] if c in loads]
        loads = loads.reset_index()
        loads = (loads.set_index("timestamp_utc").groupby(["member_id", "mode"])[cols]
                 .resample(freq).mean().reset_index())
        loads["t"] = loads["timestamp_utc"].dt.tz_convert(TZ)
        self.loads = loads.drop(columns="timestamp_utc").set_index(["member_id", "mode", "t"]).sort_index()

    def series(self, member_id: str, mode: str = "baseline", col: str = "demand_kw") -> pd.Series:
        return self.loads.loc[(member_id, mode), col]

    def modes(self, member_id: str) -> list[str]:
        return sorted(self.loads.loc[member_id].index.get_level_values("mode").unique())

    def day_index(self, date: str) -> pd.DatetimeIndex:
        start = pd.Timestamp(date, tz=TZ)
        return pd.date_range(start, start + pd.Timedelta("1D"), freq=self.freq, inclusive="left")

    def pick_peak_days(self) -> dict:
        """Winter: highest morning ISO-NE load Dec-Feb. Summer: highest afternoon load Jun-Aug."""
        g = self.grid
        win = g[(g.index.month.isin([12, 1, 2])) & (g.index.hour.isin(range(6, 11)))]["system_load_mw"]
        summ = g[(g.index.month.isin([6, 7, 8])) & (g.index.hour.isin(range(14, 19)))]["system_load_mw"]
        return {"winter": str(win.idxmax().date()), "summer": str(summ.idxmax().date())}


def weather_forecast(weather: pd.DataFrame, issue_day: str, horizon: pd.DatetimeIndex, seed: int = 0) -> pd.DataFrame:
    """Day-ahead weather forecast without leakage: measured value + one temperature error per day and a cloud factor.

    Errors are seeded by the date so every run is reproducible.
    """
    import zlib
    rng = np.random.default_rng(zlib.crc32(f"{issue_day}|{seed}".encode()))   # same forecast error every run
    fc = weather.reindex(horizon).copy()
    fc["outdoor_temp_c"] = fc["outdoor_temp_c"] + rng.normal(0, 1.5)
    cloud = float(np.clip(rng.normal(1.0, 0.15), 0.6, 1.3))
    for c in ("ghi_w_m2", "pv_per_kwdc"):
        if c in fc:
            fc[c] = fc[c] * cloud
    return fc


def eval_split(ds):
    """Whole-week split used by training AND evaluation (no leakage across days).

    test        the week around each peak day + days 15-21 of every month   (~104 days, every season)
    calibration days 8-14 of every month                                     (only for calibrating uncertainty bands)
    train       everything else
    """
    tz = ds.weather.index.tz
    all_days = list(pd.date_range(ds.weather.index[0].normalize() + pd.Timedelta("8D"),
                                  ds.weather.index[-1].normalize() - pd.Timedelta("1D"), freq="1D", tz=tz))
    peaks = ds.pick_peak_days()
    test = set()
    for d in peaks.values():
        c = pd.Timestamp(d, tz=tz)
        test |= {c + pd.Timedelta(days=k) for k in range(-3, 4)}
    test |= {d for d in all_days if 15 <= d.day <= 21}
    test &= set(all_days)
    cal = {d for d in all_days if 8 <= d.day <= 14 and d not in test}
    train = [d for d in all_days if d not in test and d not in cal]
    return all_days, train, sorted(cal), sorted(test)


def season_of(d) -> str:
    return "winter" if d.month in (12, 1, 2) else "summer" if d.month in (6, 7, 8) else "shoulder"
