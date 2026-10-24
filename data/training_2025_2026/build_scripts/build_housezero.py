#!/usr/bin/env python3
"""Build an aligned, analysis-ready HouseZero dataset (June 2025 - May 2026).

Source: Harvard Center for Green Buildings and Cities, "HouseZero one year dataset
(June 2025 - May 2026)", DOI 10.6084/m9.figshare.32790984.v1, CC BY 4.0.
Derivative work, not an official Harvard release.

Usage: python3 -I build_housezero.py RAW_DIR OUT_DIR
"""
import sys, os, re, json, math
import numpy as np
import pandas as pd

RAW, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
TZ = "America/New_York"
START_L = pd.Timestamp("2025-06-01 00:00", tz=TZ)
END_L = pd.Timestamp("2026-06-01 00:00", tz=TZ)
MIN_IDX = pd.date_range(START_L.tz_convert("UTC"), END_L.tz_convert("UTC"), freq="1min", inclusive="left")
Q_IDX = pd.date_range(START_L.tz_convert("UTC"), END_L.tz_convert("UTC"), freq="15min", inclusive="left")
KBTUH_TO_KW = 0.29307107
GPM_TO_LPS = 0.0630901964

FILES = {
    "load": "Load.csv", "weather": "Weather_station.csv", "solar": "HZ_solar_radiation.csv",
    "ztemp": "Zone_temperature.csv", "zrh": "Zone_RH.csv", "zco2": "Zone_CO2.csv",
    "window": "Zone_window.csv", "valve": "Zone_valve.csv", "slab": "Zone_slab_temperature.csv",
    "facade": "Facade_temperature.csv", "btu_tabs": "BTU_TABS.csv", "btu_geo": "BTU_GEO.csv",
}


def zone_tag(z):
    # "Z2+3+4+5" -> "z2_5", "Z12+13" -> "z12_13", "Z1" -> "z1"
    parts = z.lstrip("Zz").split("+")
    return "z" + parts[0] if len(parts) == 1 else f"z{parts[0]}_{parts[-1]}"


def snake(s):
    s = re.sub(r"[^0-9a-zA-Z]+", "_", s).strip("_").lower()
    return s


def rename(group, raw):
    """Return (new_name, unit_kind) where unit_kind in F, GPM, KBTUH, none."""
    c = re.sub(r"(\s*\([^)]*\))+\s*$", "", raw).strip()  # strip (unit) (unit) suffixes
    unit = re.findall(r"\(([^)]*)\)", raw)
    unit = unit[0] if unit else ""
    if group == "load":
        return snake(c) + "_kw", None
    if group == "weather":
        return {"Outdoor_air_temp": ("outdoor_temp_c", "F"), "Wind_speed": ("wind_m_s", None),
                "Wind_dir": ("wind_dir_deg", None), "Rain": ("rain_frac", None),
                "Gund_RH": ("rh_pct", None)}[c]
    if group == "solar":
        return "ghi_w_m2", None
    if group == "facade":
        return snake(c) + "_c", "F"
    m = re.match(r"(Z[0-9+]+)_(.*)", c)
    if m and group in ("ztemp", "zrh", "zco2", "slab", "valve", "window"):
        z, rest = zone_tag(m.group(1)), m.group(2)
        if group == "ztemp": return f"{z}_temp_c", "F"
        if group == "zrh": return f"{z}_rh_pct", None
        if group == "zco2": return f"{z}_co2_ppm", None
        if group == "slab": return f"{z}_slab_temp_c", "F"
        if group == "valve": return f"{z}_valve_pct", None
        if group == "window":
            r = rest.lower()
            if r in ("skylight", "damper"): return f"{z}_{r}_pct", None
            return f"{z}_window_{r}_pct", None
    m = re.match(r"BTU(\d+)\(([^)]*)\)_(\w+)", c)
    if m:
        n, loc, q = m.groups()
        loc = zone_tag(loc) if loc.startswith("Z") else snake(loc)
        base = f"btu{n}_{loc}"
        if q == "flow": return f"{base}_flow_l_s", "GPM"
        if q == "SupplyT": return f"{base}_supply_temp_c", "F"
        if q == "ReturnT": return f"{base}_return_temp_c", "F"
        if q == "energy": return f"{base}_energy_kw", "KBTUH"
    raise ValueError(f"unmapped column {group}:{raw}")


def load_group(group, fname):
    df = pd.read_csv(os.path.join(RAW, fname))
    t = pd.to_datetime(df.pop("Timestamp"), utc=True)
    df.index = t
    df = df.sort_index()
    ndup = int(df.index.duplicated().sum())
    df = df.groupby(level=0).mean() if ndup else df  # average exact-UTC duplicates
    cols, conv = {}, {}
    for c in df.columns:
        n, k = rename(group, c)
        cols[c] = n; conv[n] = k
    df = df.rename(columns=cols)
    df = df.apply(pd.to_numeric, errors="coerce").astype("float64")
    for n, k in conv.items():
        if k == "F": df[n] = (df[n] - 32.0) * 5.0 / 9.0
        elif k == "GPM": df[n] = df[n] * GPM_TO_LPS
        elif k == "KBTUH": df[n] = df[n] * KBTUH_TO_KW
    n_out = int((~df.index.isin(MIN_IDX)).sum())
    df = df.reindex(MIN_IDX)
    return df, {"rows_raw": int(len(t)), "dup_utc": ndup, "outside_grid": n_out}


def to_15min(df, group):
    out = {}
    g = df.groupby(df.index.floor("15min"))
    cnt = g.count()
    for c in df.columns:
        s = df[c]
        # native cadence: median spacing of valid samples (in minutes)
        v = s.dropna()
        step = max(1.0, float(np.median(np.diff(v.index.asi8[:50000])) / 6e10)) if len(v) > 10 else 1.0
        need = max(1, math.ceil((15.0 / step) * 10.0 / 15.0))
        if c == "wind_dir_deg":
            r = np.deg2rad(s)
            sm = np.sin(r).groupby(df.index.floor("15min")).mean()
            cm = np.cos(r).groupby(df.index.floor("15min")).mean()
            m = (np.rad2deg(np.arctan2(sm, cm)) + 360) % 360
        else:
            m = g[c].mean()
        m[cnt[c] < need] = np.nan
        out[c] = m
    res = pd.DataFrame(out).reindex(Q_IDX)
    res[f"valid_frac_{group}"] = (df.notna().any(axis=1).groupby(df.index.floor("15min")).mean()).reindex(Q_IDX)
    return res


def time_cols(idx):
    loc = idx.tz_convert(TZ)
    try:
        from pandas.tseries.holiday import USFederalHolidayCalendar
        hol = USFederalHolidayCalendar().holidays("2025-01-01", "2026-12-31")
        hset = set(hol.date)
    except Exception:
        hset = set()
    d = pd.DataFrame(index=idx)
    d["timestamp_utc"] = idx
    d["timestamp_local"] = loc
    d["local_date"] = loc.date
    d["local_hour"] = loc.hour
    d["weekday"] = loc.weekday  # 0=Mon
    d["us_holiday"] = [x in hset for x in loc.date]
    return d


meta = {}
parts = []
for g, f in FILES.items():
    df, info = load_group(g, f)
    meta[g] = info
    q = to_15min(df, g)
    parts.append(q)
    print(g, info, q.shape, flush=True)
    del df

all15 = pd.concat(parts, axis=1)
tc = time_cols(Q_IDX)
all15 = pd.concat([tc, all15], axis=1).reset_index(drop=True)
all15.to_parquet(os.path.join(OUT, "hz_15min_all.parquet"), index=False)


# ---------------- model table ----------------
A = all15
def S(cols):
    return A[cols].sum(axis=1, min_count=len(cols))  # NaN unless all present

def M(prefix_regex):
    cols = [c for c in A.columns if re.fullmatch(prefix_regex, c)]
    return A[cols].mean(axis=1), cols

mdl = A[["timestamp_utc", "timestamp_local", "local_date", "local_hour", "weekday", "us_holiday"]].copy()
for c in ["outdoor_temp_c", "rh_pct", "wind_m_s", "wind_dir_deg", "ghi_w_m2", "rain_frac"]:
    mdl[c] = A[c]
mdl["pv_kw"] = A["pv_meter_1_kw"].clip(lower=0) + A["pv_meter_2_kw"].clip(lower=0)
mdl["grid_net_kw"] = A["net_kw"]                       # + import, - export
mdl["grid_import_kw"] = A["in_kw"].clip(lower=0)
mdl["grid_export_kw"] = (-A["out_kw"]).clip(lower=0)  # Out is reported negative
mdl["building_demand_kw"] = A["net_kw"] + mdl["pv_kw"]
endmap = {
    "heat_pump_kw": ["heat_pump_kw", "heat_pump_electric_kw"],
    "pumps_kw": ["cooling_pump_kw"],
    "dhw_kw": ["domestic_hot_water_electric_kw", "domestic_hot_water_solar_kw"],
    "lighting_kw": ["lighting_basement_kw", "lighting_1st_kw", "lighting_2nd_kw", "lighting_3rd_kw", "emergency_lighting_kw"],
    "plugs_kw": ["plug_basement_kw", "plug_1st_kw", "plug_2nd_kw", "plug_3rd_kw"],
    "it_controls_kw": ["it_kw", "control_kw"],
    "elevator_kw": ["elevator_kw", "elevator_exhaust_fan_kw", "elevator_sump_pump_kw"],
    "other_kw": ["fire_alarm_kw", "battery_cabinet_kw", "solar_rapid_shutdown_kw"],
}
for k, v in endmap.items():
    mdl[k] = S(v).clip(lower=0)
mdl["circuits_sum_kw"] = mdl[list(endmap)].sum(axis=1, min_count=len(endmap))

floors = {"b": r"z[1-5](_\d+)?_temp_c", "f1": r"z1[1-7](_\d+)?_temp_c", "f2": r"z2[1-7](_\d+)?_temp_c", "f3": r"z3[1-3](_\d+)?_temp_c"}
mdl["indoor_temp_mean_c"], _ = M(r"z\d+(_\d+)?_temp_c")
for f, rx in floors.items():
    mdl[f"indoor_temp_{f}_mean_c"], _ = M(rx)
mdl["indoor_co2_mean_ppm"], _ = M(r"z\d+(_\d+)?_co2_ppm")
mdl["indoor_rh_mean_pct"], _ = M(r"z\d+(_\d+)?_rh_pct")
mdl["window_open_mean_pct"], _ = M(r"z\d+(_\d+)?_window_\w+_pct")
mdl["skylight_open_mean_pct"], _ = M(r"z\d+_skylight_pct")
mdl["damper_open_pct"] = A["z1_damper_pct"]
mdl["valve_open_mean_pct"], _ = M(r"z\d+(_\d+)?_valve_pct")
tabs_e = [c for c in A.columns if re.fullmatch(r"btu(5|6|7|8|10|11|13)_z.*_energy_kw", c)]
geo_e = [c for c in A.columns if re.fullmatch(r"btu(2|3)_gwell_[lr]_energy_kw", c)]
mdl["tabs_thermal_kw_total"] = A[tabs_e].sum(axis=1, min_count=len(tabs_e))
# BTU energy is reported as an unsigned magnitude; derive mode from supply vs return temperature
heat = 0.0; cool = 0.0
for c in tabs_e:
    b = c[:-len("_energy_kw")]
    dT = A[f"{b}_supply_temp_c"] - A[f"{b}_return_temp_c"]
    heat = heat + A[c].where(dT > 0, 0.0)
    cool = cool + A[c].where(dT <= 0, 0.0)
mdl["tabs_heating_kw"] = heat.where(mdl["tabs_thermal_kw_total"].notna())
mdl["tabs_cooling_kw"] = cool.where(mdl["tabs_thermal_kw_total"].notna())
mdl["geo_thermal_kw_total"] = A[geo_e].sum(axis=1, min_count=len(geo_e))
mdl["geo_common_thermal_kw"] = A["btu4_gwell_com_energy_kw"]
mdl["slab_temp_mean_c"], _ = M(r"z\d+_slab_temp_c")
mdl["facade_temp_mean_c"], _ = M(r".*_facade_.*_c")
for c in [c for c in A.columns if c.startswith("valid_frac_")]:
    mdl[c] = A[c]
mdl.to_parquet(os.path.join(OUT, "hz_15min_model.parquet"), index=False)

# hourly
num = mdl.drop(columns=["timestamp_utc", "timestamp_local", "local_date", "local_hour", "weekday", "us_holiday"])
num.index = mdl["timestamp_utc"]
key = num.index.floor("1h")
cnt = num.groupby(key).count()
hr = num.groupby(key).mean()
hr[cnt < 3] = np.nan  # need >=3 of 4 quarter-hours
sm = np.sin(np.deg2rad(num["wind_dir_deg"])).groupby(key).mean()
cm = np.cos(np.deg2rad(num["wind_dir_deg"])).groupby(key).mean()
hr["wind_dir_deg"] = ((np.rad2deg(np.arctan2(sm, cm)) + 360) % 360).where(cnt["wind_dir_deg"] >= 3)
H_IDX = pd.date_range(Q_IDX[0], Q_IDX[-1], freq="1h")
hr = hr.reindex(H_IDX)
hourly = pd.concat([time_cols(H_IDX), hr], axis=1).reset_index(drop=True)
hourly.to_parquet(os.path.join(OUT, "hz_hourly_model.parquet"), index=False)

# ---------------- data quality ----------------
dq = {"generated_from": "hz_15min_all.parquet + hz_15min_model.parquet", "parse_info": meta,
      "missing_fraction_by_month": {}, "gaps_over_2h": {}}
mon = A["timestamp_local"].dt.strftime("%Y-%m")
skip = {"timestamp_utc", "timestamp_local", "local_date", "local_hour", "weekday", "us_holiday"}
for frame in (A, mdl):
    for c in frame.columns:
        if c in skip or c in dq["missing_fraction_by_month"]:
            continue
        na = frame[c].isna()
        dq["missing_fraction_by_month"][c] = {m: round(float(v), 4) for m, v in na.groupby(mon).mean().items()}
        # gaps > 2 h (8 consecutive 15-min steps)
        a = na.values.astype(np.int8)
        d = np.diff(np.concatenate([[0], a, [0]]))
        st, en = np.where(d == 1)[0], np.where(d == -1)[0]
        tl = A["timestamp_local"]
        gl = [{"start_local": str(tl.iloc[x]), "hours": round((y - x) / 4, 2)} for x, y in zip(st, en) if y - x > 8]
        if gl:
            dq["gaps_over_2h"][c] = gl
with open(os.path.join(OUT, "data_quality.json"), "w") as f:
    json.dump(dq, f, indent=1)
print("done", all15.shape, mdl.shape, hourly.shape)
