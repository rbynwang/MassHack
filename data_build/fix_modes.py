"""Rebuild every building-mode (action) run as   baseline_2025-26 + paired effect   instead of an independent fit.

Before: each mode was its own LightGBM fit on its own ComStock run, so (mode - baseline) = true effect + two independent
fit errors; for load_shift_33 the noise was larger than the effect (eval/forecast_eval.py found corr ~0).
Now:    one LightGBM per building x mode is fit on the PAIRED 2018 difference (upgrade run - baseline run, same
        timestamps, same weather), as a share of the template's mean load; it is driven by HouseZero's measured
        2025-26 weather and added to the member's existing baseline (scaled by that member's mean load).
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import lightgbm as lgb, shutil, time
t0 = time.time()
src = open(os.path.join(os.path.dirname(__file__), "build_civic.py")).read()
exec(src[:src.index("jobs = []")])                     # ARCH, picks (same seed), meta, EU, TS, UP
exec(src[src.index("w18 = pd.read_parquet"):src.index("PRM = dict")])   # X18, X25, FC (same features)
PRM = dict(n_estimators=250, learning_rate=0.06, num_leaves=31, min_child_samples=40, subsample=0.8, subsample_freq=1,
           colsample_bytree=0.9, verbose=-1, n_jobs=2)
LP = os.path.join(OUT, "members_load_2025_2026.parquet")
bak = LP.replace(".parquet", ".before_fix_modes.parquet")
if not os.path.exists(bak):
    shutil.copy(LP, bak)
L = pd.read_parquet(bak)
for c in ("member_id", "mode"):
    L[c] = L[c].astype(str)
ts25 = pd.DatetimeIndex(wx.timestamp_utc)

def paired_effect(y0, yu):
    """Normalized paired difference model -> 2025-26 effect as a share of mean load."""
    mu = float(np.mean(y0)) or 1.0
    d = (yu - y0) / mu
    if np.abs(d).max() < 1e-6:
        return np.zeros(len(X25)), 0.0
    m = lgb.LGBMRegressor(**PRM).fit(X18[FC], d)
    return m.predict(X25[FC]), float(np.abs(d).mean())

# ---- civic: ComStock 2025 R3 timeseries already downloaded (civic_raw/<bldg>-<upgrade>.parquet) -------------------
jobs = []
for name, ids in picks.items():
    modes = ARCH[name][4]
    for k, b in enumerate(ids):
        for u, mode in UP.items():
            if mode in modes:
                jobs.append((f"{name}_{k + 1}", int(b), u, mode, "civic"))
# ---- business: datapack (ComStock 2018 runs for the 40 business templates) -------------------------------------
DPL = pd.read_parquet(os.path.join(S, "datapack/load_15min.parquet"), columns=["timestamp", "bldg_id", "upgrade", "elec_total_kw"])
have = L[L["mode"] != "baseline"].groupby("member_id")["mode"].unique().to_dict()
for mid, ms in have.items():
    if mid.startswith("cs_"):
        for mode in ms:
            u = {v: k for k, v in UP.items()}[mode]; jobs.append((mid, int(mid[3:]), u, mode, "business"))
print(len(jobs), "member x mode jobs", flush=True)

new_rows, report = [], []
for mid, b, u, mode, kind in jobs:
    if mode not in set(have.get(mid, [])):
        continue
    if kind == "civic":
        rd = lambda uu: X18[["timestamp"]].merge(
            pd.read_parquet(os.path.join(TS, f"{b}-{uu}.parquet"), columns=["timestamp", "out.electricity.total.energy_consumption"])
              .assign(timestamp=lambda x: x.timestamp.astype("datetime64[ms]")), on="timestamp", how="left")["out.electricity.total.energy_consumption"].values * 4
    else:
        g = DPL[DPL.bldg_id == b]
        rd = lambda uu: X18[["timestamp"]].merge(g[g.upgrade == uu][["timestamp", "elec_total_kw"]], on="timestamp", how="left")["elec_total_kw"].values
    y0, yu = rd(0).astype(float), rd(u).astype(float)
    ok = np.isfinite(y0) & np.isfinite(yu)
    y0, yu = np.where(ok, y0, 0), np.where(ok, yu, 0)
    eff, mag = paired_effect(y0, yu)
    base = L[(L.member_id == mid) & (L["mode"] == "baseline")].set_index("timestamp_utc").reindex(ts25)
    mean_b = float(np.nanmean(base.demand_kw.values))
    row = base.reset_index().rename(columns={"index": "timestamp_utc"})
    row["mode"] = mode
    row["demand_kw"] = np.clip(base.demand_kw.values + eff * mean_b, 0, None).astype("float32")
    new_rows.append(row[L.columns])
    old = L[(L.member_id == mid) & (L["mode"] == mode)].set_index("timestamp_utc").reindex(ts25).demand_kw.values
    report.append(dict(member=mid, mode=mode, kind=kind, true_effect_pct=round(100 * mag, 2),
                       new_effect_pct=round(100 * float(np.mean(np.abs(eff))), 2),
                       old_effect_pct=round(100 * float(np.nanmean(np.abs(old - base.demand_kw.values)) / mean_b), 2)))
    print(f"[{time.time()-t0:5.0f}s] {mid} {mode}: paired effect {100*mag:.2f}% of mean (old independent-fit diff {report[-1]['old_effect_pct']}%)", flush=True)

R = pd.DataFrame(report); R.to_csv(os.path.join(OUT, "mode_fix_report.csv"), index=False)
fixed = set(zip(R.member, R["mode"]))
keep = L[[(m, x) not in fixed for m, x in zip(L.member_id, L["mode"])]]
out = pd.concat([keep] + new_rows, ignore_index=True)
for c in ("member_id", "mode", "source"):
    out[c] = out[c].astype(str).astype("category")
check_window(out.timestamp_utc)
out.to_parquet(LP, compression="zstd", index=False)
print(R.groupby(["kind", "mode"])[["true_effect_pct", "new_effect_pct", "old_effect_pct"]].mean().round(2))
print("rows", len(out), "(before", len(L), ")")
