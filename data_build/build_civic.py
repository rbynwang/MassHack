"""Civic members: schools, libraries, fire and police stations, museums, courthouses/city offices, community centers.

Hourly profiles: NREL ComStock 2025 R3 Boston building designs used ONLY as physics templates (fit on their simulation,
then driven by HouseZero's measured 2025-26 weather), scaled to the real 2025 kWh/sq ft of the matching BERDO type.
Sizes and zips come from real BERDO 2025 buildings of that type (no names). Output replaces the business members.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import tarfile, urllib.request, json
from concurrent.futures import ThreadPoolExecutor
import lightgbm as lgb
from sklearn.metrics import r2_score

BASE = "https://oedi-data-lake.s3.amazonaws.com/"
P = "nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2025/comstock_amy2018_release_3/"
RAW = os.path.join(S, "data/raw"); TS = os.path.join(S, "civic_raw"); os.makedirs(TS, exist_ok=True)
EU = {"out.electricity.total.energy_consumption": "elec_total_kw", "out.electricity.cooling.energy_consumption": "cooling_kw",
      "out.electricity.heating.energy_consumption": "heating_kw"}

# ------------- civic archetypes: template + BERDO type + member count + role rules -------------------------------
ARCH = {
  #  name             template            BERDO type(s)                      n  battery  modes            min_soc  note
  "school":          ("SecondarySchool", ["K-12 School"],                    5, True,  ["load_shift_33", "precool_42"], 0.20, "public schools: big roofs, empty in July"),
  "library":         ("MediumOffice",    ["Library"],                        4, True,  ["load_shift_33"],              0.30, "Boston Public Library branches double as cooling centers"),
  "community_center":("RetailStandalone",["Social/Meeting Hall", "Other - Recreation"], 3, True, [],             0.30, "BCYF community centers: cooling centers in heat warnings"),
  "fire_station":    ("SmallHotel",      ["Fire Station"],                   4, True,  [],                             0.80, "critical: keeps 80% battery for outages"),
  "police_station":  ("SmallHotel",      ["Police Station"],                 3, True,  [],                             0.80, "critical: keeps 80% battery for outages"),
  "museum":          ("RetailStandalone",["Museum"],                         3, True,  [],                             0.30, "nonprofit museums: strict climate control, battery only"),
  "courthouse_office":("LargeOffice",    ["Courthouse", "Other - Public Services"], 3, True, ["load_shift_33", "precool_42"], 0.20, "courthouses and city offices"),
  "enclosed_mall":   ("RetailStripmall", ["Enclosed Mall"],                  1, True,  [],                             0.20, "enclosed mall: huge roof, air-conditioning drives the summer peak"),
  "large_retail":    ("RetailStandalone",["Retail Store"],                   3, True,  [],                             0.20, "large stores: steady all-day load, big demand charges"),
  "supermarket":     ("Grocery",         ["Supermarket/Grocery Store"],      3, True,  [],                             0.20, "supermarkets: 24/7 refrigeration, the most energy-dense type"),
  "strip_mall":      ("RetailStripmall", ["Strip Mall"],                     2, True,  [],                             0.20, "strip malls: rooftop AC, retail hours"),
}
COOLING_CENTERS = {"library", "community_center"}
BOSTON_ZIPS = {"02108", "02109", "02110", "02111", "02113", "02114", "02115", "02116", "02118", "02119", "02120", "02121", "02122",
               "02124", "02125", "02126", "02127", "02128", "02129", "02130", "02131", "02132", "02134", "02135", "02136", "02163",
               "02199", "02203", "02210", "02215", "02467"}
UP = {0: "baseline", 33: "load_shift_33", 42: "precool_42"}


def read_meta():
    f = os.path.join(RAW, "MA_G2500250_u0.tar.gz")
    if not os.path.exists(f):
        urllib.request.urlretrieve(BASE + P + "metadata_and_annual_results/by_state_and_county/basic/csv/state=MA/county=G2500250/MA_G2500250_upgrade0_basic.csv.gz", f)
    try:
        t = tarfile.open(f); df = pd.read_csv(t.extractfile(t.getmembers()[0]), low_memory=False)
    except tarfile.ReadError:
        df = pd.read_csv(f, low_memory=False)
    return df.drop_duplicates("bldg_id").set_index("bldg_id")


def get(b, u):
    f = os.path.join(TS, f"{b}-{u}.parquet")
    if not os.path.exists(f):
        urllib.request.urlretrieve(f"{BASE}{P}timeseries_individual_buildings/by_state/upgrade={u}/state=MA/{b}-{u}.parquet", f)
    return f


meta = read_meta()
listing = set()
rng = np.random.default_rng(11)
picks = {}
for name, (tmpl, _, n, *_r) in ARCH.items():
    c = meta[(meta["in.comstock_building_type"] == tmpl) & meta["in.sqft..ft2"].between(8000, 250000)]
    picks[name] = list(rng.choice(c.index.values, size=min(n, len(c)), replace=False))
print({k: len(v) for k, v in picks.items()}, flush=True)

jobs = []
for name, ids in picks.items():
    for b in ids:
        for u in [0] + [u for u, m in UP.items() if m in ARCH[name][4]]:
            jobs.append((int(b), u))
with ThreadPoolExecutor(12) as ex:
    files = list(ex.map(lambda j: (j, get(*j)), jobs))
print("downloaded", len(files), flush=True)

# ------------- fit template -> predict with HouseZero 2025-26 weather (same method as build_templates.py) ---------
w18 = pd.read_parquet(os.path.join(S, "datapack/weather_15min.parquet"))
def feats(temp, ghi, loc, hol):
    t = pd.Series(np.asarray(temp, float))
    f = pd.DataFrame({"temp": t.values, "temp_lag1h": t.shift(4).bfill().values, "temp_mean3h": t.rolling(12, min_periods=1).mean().values,
                      "temp_mean24h": t.rolling(96, min_periods=1).mean().values, "ghi": np.asarray(ghi, float),
                      "hod": (loc.hour + loc.minute / 60).values, "weekday": loc.weekday.values, "holiday": np.asarray(hol, int)})
    doy = loc.dayofyear.values
    f["season_sin"] = np.sin(2 * np.pi * doy / 365.25); f["season_cos"] = np.cos(2 * np.pi * doy / 365.25)
    wd = f.weekday.values
    daytype = np.where(f.holiday.values == 1, 2, np.where(wd == 5, 1, np.where(wd == 6, 2, 0)))
    f["occ_slot"] = daytype * 96 + loc.hour.values * 4 + loc.minute.values // 15
    return f
loc18 = pd.DatetimeIndex(w18.timestamp_utc).tz_convert(TZ) - pd.Timedelta(minutes=15)
X18 = feats(w18.temp_c, w18.ghi_wm2, loc18, w18.is_holiday); X18["timestamp"] = w18.timestamp.values
days18 = pd.Series(loc18.date); ud = days18.unique()
hold = days18.isin(set(np.random.default_rng(42).choice(ud, size=int(0.2 * len(ud)), replace=False))).values
wx = pd.read_parquet(os.path.join(OUT, "weather.parquet"))
loc25 = pd.DatetimeIndex(wx.timestamp_utc).tz_convert(TZ)
X25 = feats(wx.outdoor_temp_c, wx.ghi_w_m2.fillna(0), loc25, wx.us_holiday)
FC = list(X25.columns)
PRM = dict(n_estimators=250, learning_rate=0.08, num_leaves=63, min_child_samples=20, subsample=0.8, subsample_freq=1, colsample_bytree=0.9, verbose=-1, n_jobs=4)

# ------------- BERDO: real 2025 kWh/sq ft per type, and real sizes + zips to place members -----------------------
B = pd.read_pickle(os.path.join(S, "unified_build/_berdo_raw.pkl")) if os.path.exists(os.path.join(S, "unified_build/_berdo_raw.pkl")) else pd.read_excel(os.path.join(S, "berdo/berdo2026.xlsx"), "Buildings & Campuses")
B["kwh"] = pd.to_numeric(B["Electricity Usage (kWh)"], errors="coerce"); B["gfa"] = pd.to_numeric(B["Gross Floor Area (sq ft)"], errors="coerce")
B["zip"] = B["Building Address Zip Code"].astype(str).str.split(".").str[0].str.zfill(5)
B["kps"] = B.kwh / B.gfa

ppk = wx.pv_per_kwdc.values
rows, members, metrics = [], [], []
for name, (tmpl, btypes, n, has_bat, modes, min_soc, note) in ARCH.items():
    bt = B[B["Largest Property Type"].isin(btypes) & B.kps.between(1, 60)]
    target_kps = float(bt.kps.median())                       # real 2025 median for the type (all sizes)
    bt = bt[bt.gfa.between(5000, 1000000) & bt.zip.isin(BOSTON_ZIPS)]   # members: Boston zips, typical sizes
    sample = bt.sample(n=len(picks[name]), random_state=3, replace=len(bt) < len(picks[name]))
    for k, b in enumerate(picks[name]):
        mid = f"{name}_{k + 1}"
        preds = {}
        for u in [0] + [u for u, m in UP.items() if m in modes]:
            d = pd.read_parquet(os.path.join(TS, f"{b}-{u}.parquet"), columns=["timestamp"] + list(EU)).rename(columns=EU)
            for c in EU.values():
                d[c] = d[c] * 4
            d["timestamp"] = d["timestamp"].astype("datetime64[ms]")
            dd = X18.merge(d, on="timestamp", how="left")
            out = {}
            for tgt in EU.values():
                y = dd[tgt].values.astype(float)
                if tgt == "elec_total_kw":
                    m = lgb.LGBMRegressor(**PRM).fit(dd.loc[~hold, FC], y[~hold]); ph = m.predict(dd.loc[hold, FC])
                    metrics.append(dict(member_id=mid, archetype=name, template=tmpl, mode=UP[u], r2=r2_score(y[hold], ph),
                                        mae_pct_mean=100 * np.mean(np.abs(ph - y[hold])) / np.mean(y[hold])))
                out[tgt] = np.zeros(len(X25)) if y.max() <= 0 else np.clip(lgb.LGBMRegressor(**PRM).fit(dd[FC], y).predict(X25[FC]), 0, None)
            preds[UP[u]] = out
        tmpl_sqft = float(meta.loc[b, "in.sqft..ft2"])
        real_sqft = float(sample.iloc[k].gfa); zipc = sample.iloc[k].zip
        tmpl_kps = preds["baseline"]["elec_total_kw"].sum() / 4 / tmpl_sqft
        scale = (target_kps / tmpl_kps) * (real_sqft / tmpl_sqft)          # match BERDO kWh/sqft and the real building size
        roof_kwdc = round(min(real_sqft / 1000 * 1.5, 400), 1)            # assumption: ~1.5 kWdc per 1,000 sq ft, capped
        pv = ppk * roof_kwdc
        for mode, o in preds.items():
            rows.append(pd.DataFrame({"timestamp_utc": wx.timestamp_utc, "member_id": mid, "mode": mode,
                                      "demand_kw": (o["elec_total_kw"] * scale).astype("float32"), "pv_kw": pv.astype("float32"),
                                      "hvac_kw": ((o["cooling_kw"] + o["heating_kw"]) * scale).astype("float32"),
                                      "cooling_kw": (o["cooling_kw"] * scale).astype("float32"), "heating_kw": (o["heating_kw"] * scale).astype("float32"),
                                      "source": "simulated_template_hz_weather"}))
        base = preds["baseline"]["elec_total_kw"] * scale; pk = float(base.max())
        members.append(dict(member_id=mid, source="simulated_template_hz_weather", building_type=name, civic_role=note,
                            owner_kind="nonprofit" if name == "museum" else ("private" if name in ("enclosed_mall", "large_retail", "supermarket", "strip_mall") else "public"), template=tmpl, berdo_types="|".join(btypes),
                            sqft=round(real_sqft), zip=zipc, pv_kwdc=roof_kwdc, battery_kwh=round(2 * 0.30 * pk, 1), battery_kw=round(0.30 * pk, 1),
                            battery_label="HYPOTHETICAL: 2 h at 30% of annual peak kW", min_soc=min_soc,
                            cooling_center=name in COOLING_CENTERS, allow_building_modes=bool(modes),
                            has_modes="|".join(["baseline"] + modes), tariff_id="ma_g2_example",
                            annual_kwh_2025_26=round(base.sum() / 4), peak_kw=round(pk, 1),
                            kwh_per_sqft_2025_26=round(base.sum() / 4 / real_sqft, 2), berdo_median_kwh_per_sqft_2025=round(target_kps, 2)))
        print(mid, tmpl, round(real_sqft), zipc, "kWh/sqft", round(base.sum() / 4 / real_sqft, 2), "target", round(target_kps, 2), flush=True)

# write civic + large-retail members to their own files; build_final_members.py combines every group
M = pd.DataFrame(members)
M["group"] = M.building_type.map(lambda t: "large_retail" if t in ("enclosed_mall", "large_retail", "supermarket", "strip_mall") else "civic")
M["role"] = "prosumer"
L = pd.concat(rows, ignore_index=True)
check_window(L.timestamp_utc)
M.to_csv(os.path.join(OUT, "civic_members.csv"), index=False)
L.to_parquet(os.path.join(OUT, "civic_load.parquet"), compression="zstd", index=False)
pd.DataFrame(metrics).to_csv(os.path.join(OUT, "civic_template_fit_metrics.csv"), index=False)

# civic Boston stock: BERDO 2025 buildings of the civic types (all owners for museums; public + private K-12 noted)
rev = {t: a for a, v in ARCH.items() for t in v[1]}
C = B[B["Largest Property Type"].isin(rev) & B.zip.isin(BOSTON_ZIPS)].copy(); C["archetype"] = C["Largest Property Type"].map(rev)
st = C.groupby(["zip", "archetype"]).agg(n_buildings=("gfa", "size"), total_gfa_sqft=("gfa", "sum"), total_elec_kwh_2025=("kwh", "sum")).reset_index()
st.to_csv(os.path.join(OUT, "boston_stock_civic.csv"), index=False)
print(pd.DataFrame(metrics).groupby("archetype")[["r2", "mae_pct_mean"]].mean().round(3).to_string())
print(st.groupby("archetype")[["n_buildings", "total_gfa_sqft"]].sum().to_string())
