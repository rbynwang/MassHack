"""Second-generation forecasters, chosen by the evaluation in eval/forecast_eval.py.

GlobalLGBM   one LightGBM quantile model per building GROUP, trained on every member of the group at once (loads
             divided by each member's mean), with day-level weather (forecast high/low) and yesterday's shape.
             Pooling lets 200 training-only homes and 25 civic buildings teach each other.
Conformal    per-group widening/narrowing of the P10-P90 band so it really covers 80% on calibration weeks.
DeltaModel   the effect of an ACTION (building mode): one LightGBM per mode trained on the paired difference
             (mode run - baseline run, same building, same weather), as a share of the building's mean load.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import lightgbm as lgb

from .world_model import weather_features, calendar_features, H, QS

FEATS = ["hs", "hc", "off", "ds", "dc", "hour", "wd", "t", "cdd", "hdd", "ghi", "tmax", "tmin", "tmean",
         "lag24", "lag48", "lag168", "y_mean", "y_max", "y_min", "lw_max", "y_at_tmax"]


def _day_weather(wf_day: np.ndarray, temp_c: np.ndarray):
    return float(np.nanmax(temp_c)), float(np.nanmin(temp_c)), float(np.nanmean(temp_c))


class FeatureBuilder:
    def __init__(self, ds):
        self.ds = ds
        self.tindex = ds.weather.index
        self.pos = {t: i for i, t in enumerate(self.tindex)}
        self.cal = calendar_features(self.tindex)
        self.wf = weather_features(ds.weather)
        self.temp = ds.weather["outdoor_temp_c"].values.astype(float)
        self.hour = self.tindex.hour.values
        self.wd = self.tindex.weekday.values

    def day(self, y: np.ndarray, d, scale: float, weather_fc: pd.DataFrame | None = None):
        """Feature rows (24 x F) for the day starting at d; y is the member's hourly series aligned to tindex."""
        i = self.pos.get(d)
        if i is None or i < 8 * H or i + H > len(y):
            return None
        if weather_fc is not None:
            wf = weather_features(weather_fc); tc = weather_fc["outdoor_temp_c"].values.astype(float)
        else:
            wf = self.wf[i:i + H]; tc = self.temp[i:i + H]
        yd = y[i - H:i] / scale
        lw = y[i - 7 * H:i - 6 * H] / scale
        tmax, tmin, tmean = _day_weather(wf, tc)
        ytd_t = self.temp[i - H:i]
        y_at_tmax = yd[int(np.nanargmax(ytd_t))] if np.isfinite(ytd_t).any() and np.isfinite(yd).any() else np.nan
        X = np.column_stack([
            self.cal[i:i + H], self.hour[i:i + H], self.wd[i:i + H], wf,
            np.full(H, tmax), np.full(H, tmin), np.full(H, tmean),
            yd, y[i - 2 * H:i - H] / scale, lw,
            np.full(H, np.nanmean(yd)), np.full(H, np.nanmax(yd)), np.full(H, np.nanmin(yd)), np.full(H, np.nanmax(lw)),
            np.full(H, y_at_tmax)])
        return X.astype(np.float32)


class GlobalLGBM:
    """Pooled quantile LightGBM per group; member scale = its mean baseline load over the training days."""

    def __init__(self, ds, groups: dict, n_estimators: int = 300, lr: float = 0.05):
        self.ds, self.groups = ds, groups          # groups: member -> group name
        self.fb = FeatureBuilder(ds)
        self.models, self.scale, self.conformal = {}, {}, {}
        self.n_estimators, self.lr = n_estimators, lr

    def _y(self, m, mode="baseline"):
        return self.ds.series(m, mode).reindex(self.fb.tindex).values.astype(float)

    def _rows(self, members, days):
        Xs, ys, ms = [], [], []
        for m in members:
            y = self._y(m)
            s = self.scale[m]
            for d in days:
                X = self.fb.day(y, d, s)
                if X is None:
                    continue
                i = self.fb.pos[d]
                t = y[i:i + H] / s
                ok = np.isfinite(t)
                if ok.sum() < 20:
                    continue
                Xs.append(X[ok]); ys.append(t[ok]); ms.append(np.full(ok.sum(), m, object))
        return np.vstack(Xs), np.concatenate(ys), np.concatenate(ms)

    def fit(self, members, train_days, log=None):
        for m in members:
            y = self._y(m)
            idx = np.concatenate([np.arange(self.fb.pos[d], self.fb.pos[d] + H) for d in train_days if d in self.fb.pos])
            idx = idx[idx < len(y)]
            self.scale[m] = float(np.nanmean(y[idx])) or 1.0
        by_g = {}
        for m in members:
            by_g.setdefault(self.groups[m], []).append(m)
        for g, ms in by_g.items():
            X, t, _ = self._rows(ms, train_days)
            self.models[g] = [lgb.LGBMRegressor(objective="quantile", alpha=q, n_estimators=self.n_estimators,
                                                learning_rate=self.lr, num_leaves=63, min_child_samples=40,
                                                subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                                                n_jobs=2, verbose=-1).fit(X, t) for q in QS]
            if log:
                log(f"global lightgbm group {g}: {len(ms)} members, {len(t):,} rows")
        return self

    def calibrate(self, members, cal_days, target: float = 0.8):
        """Split-conformal: per group, find the multiplier on the band half-widths that covers `target` of hours."""
        by_g = {}
        for m in members:
            y = self._y(m)
            for d in cal_days:
                f = self.forecast(m, d, raw=True)
                if f is None:
                    continue
                i = self.fb.pos[d]; a = y[i:i + H]
                ok = np.isfinite(a)
                lo = np.maximum(f.p50.values - f.p10.values, 1e-6); hi = np.maximum(f.p90.values - f.p50.values, 1e-6)
                r = np.where(a >= f.p50.values, (a - f.p50.values) / hi, (f.p50.values - a) / lo)
                by_g.setdefault(self.groups[m], []).append(r[ok])
        for g, rs in by_g.items():
            self.conformal[g] = float(np.quantile(np.concatenate(rs), target))
        return self.conformal

    def forecast(self, member, day_start, mode="baseline", weather_fc=None, raw=False):
        s = self.scale[member]
        X = self.fb.day(self._y(member), day_start, s, weather_fc)
        if X is None:
            return None
        p = np.sort(np.stack([q.predict(X) for q in self.models[self.groups[member]]], 1), 1) * s
        idx = pd.date_range(day_start, periods=H, freq="1h")
        f = pd.DataFrame(p, index=idx, columns=["p10", "p50", "p90"])
        k = 1.0 if raw else self.conformal.get(self.groups[member], 1.0)
        if k != 1.0:
            f["p10"] = f.p50 - k * (f.p50 - f.p10); f["p90"] = f.p50 + k * (f.p90 - f.p50)
        return f.clip(lower=0)


class DeltaModel:
    """Effect of each building mode, learned from paired runs: (mode - baseline) / member mean, per hour."""

    def __init__(self, ds, fb: FeatureBuilder, scale: dict, types: dict):
        self.ds, self.fb, self.scale, self.types = ds, fb, scale, types
        self.models, self.tcode = {}, {}

    def _rows(self, mode, members, days):
        Xs, ts = [], []
        for m in members:
            yb = self.ds.series(m, "baseline").reindex(self.fb.tindex).values.astype(float)
            ym = self.ds.series(m, mode).reindex(self.fb.tindex).values.astype(float)
            s = self.scale.get(m) or float(np.nanmean(yb)) or 1.0
            tc = self.tcode.setdefault(self.types.get(m, "other"), len(self.tcode))
            for d in days:
                X = self.fb.day(yb, d, s)
                if X is None:
                    continue
                i = self.fb.pos[d]
                t = (ym[i:i + H] - yb[i:i + H]) / s
                ok = np.isfinite(t)
                if ok.sum() < 20:
                    continue
                Xs.append(np.column_stack([X, np.full(H, tc), yb[i:i + H] / s])[ok]); ts.append(t[ok])
        return (np.vstack(Xs), np.concatenate(ts)) if Xs else (None, None)

    def fit(self, mode_members: dict, train_days, log=None):
        for mode, ms in mode_members.items():
            X, t = self._rows(mode, ms, train_days)
            if X is None or len(t) < 500:
                continue
            self.models[mode] = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.05, num_leaves=63, min_child_samples=20,
                                                  n_jobs=2, verbose=-1).fit(X, t)
            if log:
                log(f"delta model {mode}: {len(ms)} members, {len(t):,} rows")
        return self

    def effect(self, member, day_start, mode, base_p50: np.ndarray, weather_fc=None):
        """Predicted change in kW per hour. Uses the BASELINE forecast as the building's expected load (no leakage)."""
        if mode not in self.models:
            return np.zeros(H)
        s = self.scale[member]
        yb = self.ds.series(member, "baseline").reindex(self.fb.tindex).values.astype(float)
        X = self.fb.day(yb, day_start, s, weather_fc)
        tc = self.tcode.get(self.types.get(member, "other"), -1)
        X = np.column_stack([X, np.full(H, tc), np.asarray(base_p50) / s])
        return self.models[mode].predict(X) * s


class ForecasterV2:
    """Planner forecaster: GlobalLGBM baseline (calibrated) + DeltaModel action effects."""

    def __init__(self, base: GlobalLGBM, delta: DeltaModel | None, fallback=None):
        self.base, self.delta, self.fallback = base, delta, fallback
        self.base_name = "global lightgbm (calibrated)"

    def forecast(self, member, day_start, mode="baseline", weather_fc=None):
        b = self.base.forecast(member, day_start, "baseline", weather_fc)
        if b is None and self.fallback is not None:
            return self.fallback.forecast(member, day_start, mode, weather_fc)
        if mode == "baseline" or self.delta is None:
            return b
        eff = self.delta.effect(member, day_start, mode, b.p50.values, weather_fc)
        return (b + eff[:, None]).clip(lower=0)


class Calibrated:
    """Split-conformal wrapper: widen/narrow any forecaster's P10-P90 band per building group to cover `target`."""

    def __init__(self, base, groups: dict):
        self.base, self.groups, self.k = base, groups, {}

    def calibrate(self, ds, members, cal_days, target: float = 0.8, weather_fn=None):
        res = {}
        for m in members:
            for d in cal_days:
                idx = ds.day_index(str(d.date()))
                a = ds.series(m).reindex(idx).values
                if np.isnan(a).any():
                    continue
                f = self.base.forecast(m, d, "baseline", weather_fn(d) if weather_fn else None)
                lo = np.maximum(f.p50.values - f.p10.values, 1e-6); hi = np.maximum(f.p90.values - f.p50.values, 1e-6)
                r = np.where(a >= f.p50.values, (a - f.p50.values) / hi, (f.p50.values - a) / lo)
                res.setdefault(self.groups[m], []).append(r)
        self.k = {}
        for g, v in res.items():
            r = np.concatenate(v); r = r[np.isfinite(r)]
            self.k[g] = float(np.quantile(r, target)) if len(r) else 1.0
        return self.k

    def forecast(self, member, day_start, mode="baseline", weather_fc=None):
        f = self.base.forecast(member, day_start, mode, weather_fc).copy()
        k = self.k.get(self.groups.get(member), 1.0)
        f["p10"] = f.p50 - k * (f.p50 - f.p10); f["p90"] = f.p50 + k * (f.p90 - f.p50)
        return f.clip(lower=0)


class EffectForecaster:
    """Planner forecaster: calibrated baseline + the change each action causes, from the model that predicts that
    action best on held-out days (world model or paired-difference LightGBM)."""

    def __init__(self, base, wm, delta, choice: dict, base_name: str):
        self.base, self.wm, self.delta, self.choice, self.base_name = base, wm, delta, choice, base_name

    def effect(self, member, day_start, mode, b, weather_fc=None):
        src = self.choice.get(mode, "world_model")
        if src == "delta_lgbm" and self.delta is not None and mode in self.delta.models:
            return self.delta.effect(member, day_start, mode, b.p50.values, weather_fc)
        if src == "none":
            return np.zeros(len(b))
        wb = self.wm.forecast(member, day_start, "baseline", weather_fc); wm_ = self.wm.forecast(member, day_start, mode, weather_fc)
        return (wm_["p50"] - wb["p50"]).values

    def forecast(self, member, day_start, mode="baseline", weather_fc=None):
        b = self.base.forecast(member, day_start, "baseline", weather_fc)
        if mode == "baseline":
            return b
        return (b + self.effect(member, day_start, mode, b, weather_fc)[:, None]).clip(lower=0)
