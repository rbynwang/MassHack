"""HouseZero May 2025 (from the June 2024 - May 2025 release, as committed in the team repo) in the same 15-min model format,
then prepend it to the June 2025 - May 2026 table -> hz_15min_model_13m.parquet."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
T = os.path.join(S, "team/data/housezero")
def minute(f):
    d = pd.read_csv(os.path.join(T, f)); d["timestamp_utc"] = pd.to_datetime(d.timestamp_utc, utc=True); return d.set_index("timestamp_utc")
e, w, r = minute("energy_minute.csv.gz"), minute("weather_minute.csv.gz"), minute("radiation_minute.csv.gz")
h = pd.read_csv(os.path.join(T, "energy_hourly.csv")); h["timestamp_utc"] = pd.to_datetime(h.timestamp_utc, utc=True); h = h.set_index("timestamp_utc")
a, b = pd.Timestamp("2025-05-01", tz=TZ).tz_convert("UTC"), pd.Timestamp("2025-06-01", tz=TZ).tz_convert("UTC")
idx = pd.date_range(a, b, freq="15min", inclusive="left", name="timestamp_utc")
def agg(s, kind="mean"):
    s = s[(s.index >= a) & (s.index < b)]
    g = s.resample("15min"); m = g.mean(); n = g.count()
    return m.where(n >= 10).reindex(idx)
pv = (agg(e["PV_meter_1 (kW)"]) + agg(e["PV_meter_2 (kW)"])).clip(lower=0)
net = agg(e["Net (kW)"])
out = pd.DataFrame(index=idx)
out["outdoor_temp_c"] = (agg(w["Outdoor_air_temp (°F)"]) - 32) * 5 / 9
out["rh_pct"] = w["Relative_humidity (%)"][(w.index >= a) & (w.index < b)].resample("15min").mean().reindex(idx)
out["wind_m_s"] = agg(w["Wind_speed (m_s)"]); out["rain_frac"] = agg(w["Rain (Boolean)"])
out["ghi_w_m2"] = agg(r["HZ_solar_radiation (W_m^2)"])
out["pv_kw"] = pv; out["grid_net_kw"] = net; out["building_demand_kw"] = net + pv
hh = h[(h.index >= a) & (h.index < b)]
for col, src in (("heat_pump_kw", ["Heat_pump (kW)"]), ("pumps_kw", ["Cooling_pump (kW)"])):
    out[col] = hh[src].sum(axis=1, min_count=1).reindex(idx, method="ffill")
hz = pd.read_parquet(os.path.join(S, "hz_out/hz_15min_model.parquet")).set_index("timestamp_utc")
full = pd.concat([out, hz], axis=0).sort_index()
full = full[~full.index.duplicated()]
full.reset_index().to_parquet(os.path.join(S, "hz_out/hz_15min_model_13m.parquet"), index=False)
print(len(out), "May rows | missing temp", int(out.outdoor_temp_c.isna().sum()), "demand", int(out.building_demand_kw.isna().sum()),
      "| May mean demand kW", round(out.building_demand_kw.mean(), 2), "| total rows", len(full), full.index.min(), full.index.max())
