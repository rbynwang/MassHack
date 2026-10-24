"""ISO-NE RT hourly LMP (.Z.NEMASSBOST) + system load -> 15-min grid; synthetic DR calendar from real 2025-26 load."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import json, glob
G = os.path.join(S, "g2526")
def load_any(kind):
    f = os.path.join(G, f"isone_{kind}_2025_2026.parquet")
    files = [f] if os.path.exists(f) else sorted(glob.glob(os.path.join(G, f"{kind}_2*.parquet")))
    return pd.concat([pd.read_parquet(x) for x in files]), [os.path.basename(x) for x in files]
idx = grid_index(); g = calendar(idx)
ld, ld_files = load_any("load"); lm, lm_files = load_any("lmp")
ld["ts"] = pd.to_datetime(ld["Interval Start"], utc=True); ld = ld.drop_duplicates("ts").set_index("ts").sort_index()
load15 = ld.Load.resample("15min").mean(); n5 = ld.Load.resample("15min").count()
g["system_load_mw"] = load15.reindex(idx).astype("float32"); g["load_n5min"] = n5.reindex(idx).fillna(0).astype("int8")
lm["ts"] = pd.to_datetime(lm["Interval Start"], utc=True); lm = lm.drop_duplicates("ts").set_index("ts").sort_index()
lm = lm[(lm.index >= idx[0]) & (lm.index <= idx[-1])]
hourly = pd.date_range(idx[0], idx[-1], freq="1h")
have_h = hourly.isin(lm.index)
last_avail = lm.index.max()
for c, n in (("LMP","lmp_usd_mwh"),("Energy","lmp_energy_usd_mwh"),("Congestion","lmp_congestion_usd_mwh"),("Loss","lmp_loss_usd_mwh")):
    h = lm[c].reindex(hourly)
    h[hourly <= last_avail] = h[hourly <= last_avail].ffill()      # fill isolated missing source hours
    g[n] = h.reindex(idx, method="ffill").astype("float32")
    g.loc[idx > last_avail + pd.Timedelta(minutes=45), n] = np.nan   # never extrapolate beyond downloaded months
g["lmp_source_hour_missing"] = ~pd.Series(have_h, index=hourly).reindex(idx, method="ffill").values
# flags
lh = g.system_load_mw.resample("1h").mean()
thr_load = lh.quantile(0.95); stress_h = lh[lh >= thr_load].index
g["grid_stress"] = g.index.floor("1h").isin(stress_h)
p95 = float(np.nanpercentile(g.lmp_usd_mwh, 95)); g["price_spike"] = g.lmp_usd_mwh > p95
# synthetic DR calendar
loc = ld.index.tz_convert(TZ)
dl = pd.DataFrame({"load": ld.Load.values, "date": loc.date, "hour": loc.hour, "month": loc.month, "wd": loc.weekday}, index=loc)
from pandas.tseries.holiday import USFederalHolidayCalendar
hol = set(USFederalHolidayCalendar().holidays("2025-01-01","2026-12-31").date)
ok = (dl.wd < 5) & ~dl.date.isin(hol)
summer = dl[ok & (dl.index >= pd.Timestamp("2025-06-01", tz=TZ)) & (dl.index < pd.Timestamp("2025-10-01", tz=TZ))]
s_days = summer.groupby("date").load.max().nlargest(40)
winter = dl[ok & (dl.index >= pd.Timestamp("2025-12-01", tz=TZ)) & (dl.index < pd.Timestamp("2026-03-01", tz=TZ)) & dl.hour.between(6,9)]
w_days = winter.groupby("date").load.max().nlargest(10)
rows = []
for prog, days, (h0, h1) in (("summer_connectedsolutions_style_SYNTHETIC", s_days, (15,18)), ("winter_morning_HYPOTHETICAL_SYNTHETIC", w_days, (7,9))):
    for r, (d, v) in enumerate(days.sort_index().items()):
        st = pd.Timestamp(f"{d} {h0:02d}:00", tz=TZ); en = pd.Timestamp(f"{d} {h1:02d}:00", tz=TZ)
        rows.append(dict(date=str(d), program=prog, start_local=st.isoformat(), end_local=en.isoformat(),
                         start_utc=st.tz_convert("UTC").isoformat(), end_utc=en.tz_convert("UTC").isoformat(),
                         selection_load_mw=round(float(v),1), selection_rank=int(days.rank(ascending=False)[d]), synthetic=True))
dr = pd.DataFrame(rows); dr.to_csv(os.path.join(OUT, "dr_events_2025.csv"), index=False)
g["dr_event_summer"] = False; g["dr_event_winter"] = False
for _, r in dr.iterrows():
    m = (g.index >= pd.Timestamp(r.start_utc)) & (g.index < pd.Timestamp(r.end_utc))
    g.loc[m, "dr_event_summer" if r.program.startswith("summer") else "dr_event_winter"] = True
g = g.reset_index(); check_window(g.timestamp_utc)
g.to_parquet(os.path.join(OUT, "grid.parquet"), compression="zstd", index=False)
months = pd.period_range("2025-06", "2026-05", freq="M")
lm_months = sorted(set(lm.index.tz_convert(TZ).to_period("M").astype(str)))
rep = dict(load_files=ld_files, lmp_files=lm_files, lmp_months_present=lm_months,
           lmp_months_missing=[str(m) for m in months if str(m) not in lm_months],
           lmp_hours_missing_within_downloaded=int((~have_h[hourly <= last_avail]).sum()),
           load_15min_missing=int(g.system_load_mw.isna().sum()), load_15min_partial=int((g.load_n5min.between(1,2)).sum()),
           grid_stress_threshold_mw=round(float(thr_load),1), grid_stress_hours=int(len(stress_h)),
           price_spike_p95_usd_mwh=round(p95,2), lmp_mean=round(float(np.nanmean(g.lmp_usd_mwh)),2),
           lmp_max=round(float(np.nanmax(g.lmp_usd_mwh)),2), lmp_min=round(float(np.nanmin(g.lmp_usd_mwh)),2),
           system_load_peak_mw=round(float(g.system_load_mw.max()),1), system_load_peak_time=str(g.loc[g.system_load_mw.idxmax(),"timestamp_local"]),
           dr_summer_days=len(s_days), dr_winter_days=len(w_days))
json.dump(rep, open(os.path.join(S,"unified_build/_grid_report.json"),"w"), indent=1); print(json.dumps(rep, indent=1))
