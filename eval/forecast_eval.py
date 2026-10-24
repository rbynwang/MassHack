"""Experiment 3: baseline forecasters on ~100 held-out days (peak weeks + one week per month).
Experiment 4: action-effect models (paired-difference LightGBM) on the same held-out days."""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "eval"))
DATA = os.environ.get("MASSHACK_DATA", str(ROOT / "data" / "model_inputs"))
import sys, time, pickle, numpy as np, pandas as pd
from common import split, season, Dataset
from masshack.data import weather_forecast
from masshack.forecast import LGBMForecaster, seasonal_naive
from masshack.forecast_v2 import GlobalLGBM, DeltaModel
from run_all import member_type
t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:6.1f}s]", *a, flush=True)
ds = Dataset(DATA); train, cal, test, peaks = split(ds)
M = ds.members; comm = [m for m in M.index if bool(M.loc[m, "in_community"])]
allm = list(M.index); groups = {m: M.loc[m, "group"] for m in allm}
types = {m: member_type(r) for m, r in M.iterrows()}
log(f"train {len(train)} days · cal {len(cal)} · test {len(test)} · community {len(comm)} · all {len(allm)}")

g = GlobalLGBM(ds, groups).fit(allm, train, log=log)
conf = g.calibrate(comm, cal); log("conformal multipliers", {k: round(v, 2) for k, v in conf.items()})
per = LGBMForecaster(ds)
for m in comm: per.fit(m, train, "baseline")
log("per-member lightgbm trained")
pickle.dump({"global": g}, open("eval/global_lgbm.pkl", "wb"))

rows = []; agg = {}
for d in test:
    wfc = weather_forecast(ds.weather, str(d.date()), ds.day_index(str(d.date())))
    for m in comm:
        y = ds.series(m).reindex(ds.day_index(str(d.date()))).values
        if np.isnan(y).any() or y.mean() <= 0: continue
        P = {"per_member_lgbm (current)": per.forecast(m, d, "baseline", wfc), "global_lgbm": g.forecast(m, d, weather_fc=wfc, raw=True),
             "global_lgbm_calibrated": g.forecast(m, d, weather_fc=wfc), "same_hour_last_week": seasonal_naive(ds.series(m), d)}
        for k, f in P.items():
            if f is None or f.isna().any().any(): continue
            p10, p50, p90 = f.p10.values, f.p50.values, f.p90.values; mu = y.mean()
            pin = sum(np.mean(np.maximum(q * (y - p), (q - 1) * (y - p))) for q, p in ((0.1, p10), (0.5, p50), (0.9, p90))) / mu * 100
            rows.append(dict(model=k, member=m, group=groups[m], season=season(d), date=str(d.date()), mae=np.mean(abs(p50 - y)) / mu * 100,
                             peak_err=abs(p50.max() - y.max()) / y.max() * 100, peak_bias=(p50.max() - y.max()) / y.max() * 100,
                             pinball=pin, cov=np.mean((y >= p10) & (y <= p90)), p90_peak_ok=float(y.max() <= p90.max())))
            a = agg.setdefault((k, str(d.date())), [0, 0]); a[0] = a[0] + y; a[1] = a[1] + p50
R = pd.DataFrame(rows); R.to_csv("eval/forecast_eval.csv", index=False)
C = pd.DataFrame([dict(model=k, date=dd, mae=np.mean(abs(v[1] - v[0])) / v[0].mean() * 100, peak_err=abs(v[1].max() - v[0].max()) / v[0].max() * 100)
                  for (k, dd), v in agg.items()])
pd.set_option("display.width", 200)
print("\n=== all community members, held-out days (mean over member-days) ===")
print(R.groupby("model")[["mae", "peak_err", "peak_bias", "pinball", "cov", "p90_peak_ok"]].mean().round(2))
print("\n=== MAE % by group ==="); print(R.pivot_table(index="group", columns="model", values="mae").round(1))
print("\n=== daily-peak error % by group ==="); print(R.pivot_table(index="group", columns="model", values="peak_err").round(1))
print("\n=== coverage by group (target 0.80) ==="); print(R.pivot_table(index="group", columns="model", values="cov").round(2))
print("\n=== MAE % by season ==="); print(R.pivot_table(index="season", columns="model", values="mae").round(1))
print("\n=== community total (sum of members) ==="); print(C.groupby("model")[["mae", "peak_err"]].mean().round(2))

# ---------------- Experiment 4: action effects ------------------------------------------------------------
mode_members = {}
for m in allm:
    for x in ds.modes(m):
        if x != "baseline": mode_members.setdefault(x, []).append(m)
log("modes", {k: len(v) for k, v in mode_members.items()})
dm = DeltaModel(ds, g.fb, g.scale, types).fit(mode_members, train, log=log)
pickle.dump(dm, open("eval/delta_model.pkl", "wb"))
er = []
for d in test:
    wfc = weather_forecast(ds.weather, str(d.date()), ds.day_index(str(d.date())))
    idx = ds.day_index(str(d.date()))
    for mode, ms in mode_members.items():
        for m in ms:
            if m not in comm: continue
            yb = ds.series(m).reindex(idx).values; ym = ds.series(m, mode).reindex(idx).values
            if np.isnan(yb).any() or np.isnan(ym).any(): continue
            act = ym - yb
            if np.abs(act).max() < 1e-6: continue
            b = g.forecast(m, d, weather_fc=wfc)
            pe = dm.effect(m, d, mode, b.p50.values, wfc)
            pk = int(np.argmax(yb)); sc = yb.max()
            er.append(dict(model="delta_lgbm", mode=mode, member=m, date=str(d.date()), corr=np.corrcoef(pe, act)[0, 1] if act.std() > 0 else np.nan,
                           mae_pct_peak=np.mean(abs(pe - act)) / sc * 100, peakhr_err_pct=(pe[pk] - act[pk]) / sc * 100,
                           sign_ok=float(np.sign(round(pe[pk], 6)) == np.sign(round(act[pk], 6))), pred_peakhr=pe[pk], act_peakhr=act[pk]))
E=pd.DataFrame(er); E.to_csv("eval/effects_delta.csv", index=False)
print("\n=== action effects: paired-difference LightGBM (held-out days) ===")
print(E.groupby("mode").agg(n=("member", "size"), corr=("corr", "median"), mae_pct_of_peak=("mae_pct_peak", "mean"),
                            sign_ok_at_peak=("sign_ok", "mean"), pred_kw_at_peak=("pred_peakhr", "sum"), act_kw_at_peak=("act_peakhr", "sum")).round(2))
log("done")
