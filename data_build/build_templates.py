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
P = dict(n_estimators=250, learning_rate=0.08, num_leaves=63, min_child_samples=20, subsample=0.8, subsample_freq=1,
         colsample_bytree=0.9, verbose=-1, n_jobs=2)
MODE = {0: "baseline", 33: "load_shift_33", 42: "precool_42"}
metrics, outs, annual = [], [], []
for (b, u), g in L.groupby(["bldg_id", "upgrade"]):
    g = g.sort_values("timestamp"); assert len(g) == 35040
    d = X18.merge(g, on="timestamp", how="left"); btype = bl.building_type[b]; preds = {}
    for tgt, src in (("demand_kw", "elec_total_kw"), ("cooling_kw", "cooling_kw"), ("heating_kw", "heating_kw")):
        y = d[src].values.astype(float)
        if tgt == "demand_kw":
            m = lgb.LGBMRegressor(**P).fit(d.loc[~is_hold, FC], y[~is_hold]); ph = m.predict(d.loc[is_hold, FC]); yh = y[is_hold]
            metrics.append(dict(bldg_id=b, building_type=btype, mode=MODE[u], r2=r2_score(yh, ph),
                                mae_pct_mean=100*np.mean(np.abs(ph-yh))/np.mean(yh)))
        if y.max() <= 0: preds[tgt] = np.zeros(len(X25)); continue
        m = lgb.LGBMRegressor(**P).fit(d[FC], y)
        preds[tgt] = np.clip(m.predict(X25[FC]), 0, None)
    annual.append(dict(bldg_id=b, building_type=btype, mode=MODE[u], sqft=bl.sqft[b], kwh_2025_26=preds["demand_kw"].sum()/4,
                       ratio_vs_template=preds["demand_kw"].sum()/d.elec_total_kw.sum()))
    outs.append(pd.DataFrame({"timestamp_utc": wx.timestamp_utc, "member_id": f"cs_{b}", "mode": MODE[u],
        "demand_kw": preds["demand_kw"].astype("float32"), "cooling_kw": preds["cooling_kw"].astype("float32"),
        "heating_kw": preds["heating_kw"].astype("float32")}))
    print(b, u, round(metrics[-1]["r2"], 3), flush=True)
out = pd.concat(outs, ignore_index=True)
check_window(out.timestamp_utc)
out.to_parquet(os.path.join(S, "unified_build/_business_load.parquet"), compression="zstd", index=False)
met = pd.DataFrame(metrics); an = pd.DataFrame(annual)
met.to_csv(os.path.join(OUT, "template_fit_metrics.csv"), index=False)
an.to_csv(os.path.join(S, "unified_build/_annual_by_member.csv"), index=False)
fit_t = met.groupby(["building_type","mode"])[["r2","mae_pct_mean"]].agg(["mean","min","max"]).round(3)
an["kwh_per_sqft"] = an.kwh_2025_26/an.sqft
an_t = an.groupby(["building_type","mode"]).agg(n=("bldg_id","size"), kwh_2025_26_total=("kwh_2025_26","sum"),
        kwh_per_sqft_median=("kwh_per_sqft","median"), ratio_2025_26_vs_template_2018=("ratio_vs_template","mean")).round(3).reset_index()
# sanity: peaks vs hottest afternoons; summer/winter monthly peak ratio
base = out[out["mode"]=="baseline"].merge(an[an["mode"]=="baseline"][["bldg_id"]].assign(member_id=lambda z: "cs_"+z.bldg_id.astype(str)), on="member_id")
base["btype"] = base.bldg_id.map(bl.building_type)
lt = pd.DatetimeIndex(wx.timestamp_utc).tz_convert(TZ)
T = pd.Series(wx.outdoor_temp_c.values, index=lt)
sanity = {}
for bt, gg in base.groupby("btype"):
    s = pd.Series(gg.groupby("timestamp_utc").demand_kw.sum().values, index=lt)
    mon = s.resample("MS").max()
    summer = mon[mon.index.month.isin([6,7,8])].mean(); winter = mon[mon.index.month.isin([12,1,2])].mean()
    sm = s[(s.index.month>=6)&(s.index.month<=9)]
    pk = sm.resample("1D").max(); tmax = T[(T.index.month>=6)&(T.index.month<=9)].resample("1D").max()
    top_l = set(pk.nlargest(10).index.date); top_t = set(tmax.nlargest(10).index.date)
    sanity[bt] = dict(summer_winter_monthly_peak_ratio=round(float(summer/winter),2),
                      peak_hour_local=int(sm.idxmax().hour), peak_day=str(sm.idxmax().date()),
                      top10_load_vs_top10_hot_overlap=len(top_l & top_t),
                      corr_daily_peak_vs_tmax=round(float(np.corrcoef(pk.values, tmax.values)[0,1]),3))
rep = dict(fit_by_type=fit_t.reset_index().to_dict("records"), annual_by_type=an_t.to_dict("records"), sanity=sanity,
           hottest_days_2025=sorted(map(str, T[(T.index.month>=6)&(T.index.month<=9)].resample("1D").max().nlargest(5).index.date)))
json.dump(rep, open(os.path.join(S, "unified_build/_templates_report.json"), "w"), indent=1, default=str)
print(fit_t.to_string()); print(an_t.to_string()); print(json.dumps(sanity, indent=1))
