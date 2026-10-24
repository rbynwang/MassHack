"""Baseline forecasters with the same interface as the world model: seasonal-naive and LightGBM quantiles."""
from __future__ import annotations

import numpy as np
import pandas as pd
import lightgbm as lgb

from .world_model import weather_features, calendar_features, H, QS


def seasonal_naive(series: pd.Series, day_start: pd.Timestamp) -> pd.DataFrame:
    """Same hour last week."""
    idx = pd.date_range(day_start, periods=H, freq=series.index.freq or "1h")
    v = series.reindex(idx - pd.Timedelta("7D")).values
    return pd.DataFrame({"p10": v, "p50": v, "p90": v}, index=idx)


class LGBMForecaster:
    """One quantile model per member: weather + calendar + same-hour lags (yesterday, last week)."""

    def __init__(self, ds, use_weather: bool = True):
        self.ds, self.use_weather = ds, use_weather
        self.models = {}
        self.wf = pd.DataFrame(weather_features(ds.weather), index=ds.weather.index, columns=["t", "cdd", "hdd", "ghi"])
        self.cal = pd.DataFrame(calendar_features(ds.weather.index), index=ds.weather.index, columns=["hs", "hc", "off", "ds", "dc"])

    def _X(self, y: pd.Series, idx, wf=None):
        X = self.cal.reindex(idx).copy()
        if self.use_weather:
            X = X.join((wf if wf is not None else self.wf).reindex(idx))
        X["lag24"] = y.reindex(idx - pd.Timedelta("1D")).values
        X["lag168"] = y.reindex(idx - pd.Timedelta("7D")).values
        return X

    def fit(self, member: str, train_days, mode: str = "baseline"):
        y = self.ds.series(member, mode).reindex(self.ds.weather.index)
        idx = pd.DatetimeIndex(np.concatenate([pd.date_range(d, periods=H, freq="1h") for d in train_days]))
        idx = idx[idx.isin(y.index)].unique().sort_values()   # daylight-saving days overlap by an hour
        X, t = self._X(y, idx), y.reindex(idx)
        ok = t.notna().values
        self.models[(member, mode)] = [lgb.LGBMRegressor(objective="quantile", alpha=q, n_estimators=150, learning_rate=0.07, n_jobs=2,
                                                         num_leaves=31, min_child_samples=10, verbose=-1).fit(X[ok], t[ok]) for q in QS]
        return self

    def forecast(self, member: str, day_start: pd.Timestamp, mode: str = "baseline", weather_fc: pd.DataFrame | None = None):
        y = self.ds.series(member, mode).reindex(self.ds.weather.index)
        idx = pd.date_range(day_start, periods=H, freq="1h")
        wf = None
        if weather_fc is not None:
            wf = pd.DataFrame(weather_features(weather_fc), index=weather_fc.index, columns=["t", "cdd", "hdd", "ghi"])
        X = self._X(y, idx, wf)
        p = np.sort(np.stack([m.predict(X) for m in self.models[(member, mode)]], 1), 1)
        return pd.DataFrame(p, index=idx, columns=["p10", "p50", "p90"]).clip(lower=0)


class HybridForecaster:
    """Baseline load from the most accurate model; the effect of an ACTION (building mode) from the world model.

    forecast(member, day, mode) = base(member, day) + [WM(member, day, mode) - WM(member, day, baseline)]
    This is how the world model drives decisions: it imagines what each candidate action does to the load, and the
    planner and coordinator choose actions from those imagined effects.
    """

    def __init__(self, base, world_model, base_name: str = "lightgbm"):
        self.base, self.wm, self.base_name = base, world_model, base_name

    def forecast(self, member, day_start, mode="baseline", weather_fc=None):
        b = self.base.forecast(member, day_start, "baseline", weather_fc)
        if mode == "baseline":
            return b
        wm_b = self.wm.forecast(member, day_start, "baseline", weather_fc)
        wm_m = self.wm.forecast(member, day_start, mode, weather_fc)
        delta = (wm_m["p50"] - wm_b["p50"]).values
        return (b + delta[:, None]).clip(lower=0)
