"""ComStock 2025 R3 Boston buildings used as PHYSICS TEMPLATES only.
Fit a weather+calendar response model per building x upgrade on the 2018 simulation (fitting material only),
then drive it with HouseZero's MEASURED 2025-06..2026-05 weather. No 2018 timestamps, weather or loads are exported."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import json, lightgbm as lgb
from sklearn.metrics import r2_score
DP = os.path.join(S, "datapack")
bl = pd.read_csv(os.path.join(DP, "buildings.csv")).set_index("bldg_id")
w18 = pd.read_parquet(os.path.join(DP, "weather_15min.parquet"))
L = pd.read_parquet(os.path.join(DP, "load_15min.parquet"), columns=["timestamp","bldg_id","upgrade","elec_total_kw","cooling_kw","heating_kw"])
L = L[L.upgrade.isin([0,33,42])]

def feats(temp, ghi, loc, hol):
    t = pd.Series(np.asarray(temp, float))
    f = pd.DataFrame({"temp": t.values, "temp_lag1h": t.shift(4).bfill().values,
        "temp_mean3h": t.rolling(12, min_periods=1).mean().values, "temp_mean24h": t.rolling(96, min_periods=1).mean().values,
        "ghi": np.asarray(ghi, float), "hod": (loc.hour + loc.minute/60).values, "weekday": loc.weekday.values,
        "holiday": np.asarray(hol, int)})
    doy = loc.dayofyear.values
    f["season_sin"] = np.sin(2*np.pi*doy/365.25); f["season_cos"] = np.cos(2*np.pi*doy/365.25)
    wd = f.weekday.values
    daytype = np.where(f.holiday.values == 1, 2, np.where(wd == 5, 1, np.where(wd == 6, 2, 0)))
    f["occ_slot"] = daytype*96 + loc.hour.values*4 + loc.minute.values//15   # hour x day-type occupancy proxy
    return f

loc18 = pd.DatetimeIndex(w18.timestamp_utc).tz_convert(TZ) - pd.Timedelta(minutes=15)   # interval START wall clock
X18 = feats(w18.temp_c, w18.ghi_wm2, loc18, w18.is_holiday); X18["timestamp"] = w18.timestamp.values
days18 = pd.Series(loc18.date); rng = np.random.default_rng(42); ud = days18.unique()
is_hold = days18.isin(set(rng.choice(ud, size=int(0.2*len(ud)), replace=False))).values
wx = pd.read_parquet(os.path.join(OUT, "weather.parquet"))
loc25 = pd.DatetimeIndex(wx.timestamp_utc).tz_convert(TZ)
X25 = feats(wx.outdoor_temp_c, wx.ghi_w_m2.fillna(0), loc25, wx.us_holiday)
FC = list(X25.columns)
P = dict(n_estimators=120, learning_rate=0.12, num_leaves=63, min_child_samples=20, subsample=0.8, subsample_freq=1,
         colsample_bytree=0.9, verbose=-1, n_jobs=2)
MODE = {0: "baseline", 33: "load_shift_33", 42: "precool_42"}
metrics, outs, annual = [], [], []
for (b, u), g in L.groupby(["bldg_id", "upgrade"]):
    g = g.sort_values("timestamp"); assert len(g) == 35040
    d = X18.merge(g, on="timestamp", how="left"); btype = bl.building_type[b]; preds = {}
    for tgt, src in (("demand_kw", "elec_total_kw"),):
        y = d[src].values.astype(float)
        # held-out fit check already done in the full run (template_fit_metrics.csv)
        if y.max() <= 0: preds[tgt] = np.zeros(len(X25)); continue
        m = lgb.LGBMRegressor(**P).fit(d[FC], y)
        preds[tgt] = np.clip(m.predict(X25[FC]), 0, None)
    annual.append(dict(bldg_id=b, building_type=btype, mode=MODE[u], sqft=bl.sqft[b], kwh_2025_26=preds["demand_kw"].sum()/4,
                       ratio_vs_template=preds["demand_kw"].sum()/d.elec_total_kw.sum()))
    outs.append(pd.DataFrame({"timestamp_utc": wx.timestamp_utc, "member_id": f"cs_{b}", "mode": MODE[u],
        "demand_kw": preds["demand_kw"].astype("float32"), "cooling_kw": np.full(len(X25), np.nan, "float32"),
        "heating_kw": np.full(len(X25), np.nan, "float32")}))
    print(b, u, "done", flush=True)
out = pd.concat(outs, ignore_index=True)
check_window(out.timestamp_utc)
out.to_parquet(os.path.join(S, "unified_build/_business_load.parquet"), compression="zstd", index=False)
print("annual by type", pd.DataFrame(annual).groupby(["building_type","mode"]).kwh_2025_26.sum().round(0).to_string())
