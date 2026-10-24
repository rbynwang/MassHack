"""Combine every member group into members.csv + members_load_2025_2026.parquet (May 2025 - May 2026).

Groups
  housezero        measured (HouseZero, Cambridge) - from build_members.py
  small_business   40 NREL ComStock designs driven by HouseZero weather - from build_members.py
  civic            25 public/nonprofit buildings (templates) - from build_civic.py
  large_retail     9 malls, large stores, supermarkets, strip malls (templates) - from build_civic.py
  civic_measured   Boston Public Library Central Library, measured 5-min meter (City of Boston, PDDL)
  home             40 synthetic single-family homes in the community + 200 training-only homes (homesim, teammate's
                   generator, seed 42), with an evening-peak calibration toward National Grid R-1 and, for the
                   training-only copy, sensor noise and gaps.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import json, glob

idx = grid_index()
rng = np.random.default_rng(2026)
cols = ["timestamp_utc", "member_id", "mode", "demand_kw", "pv_kw", "hvac_kw", "cooling_kw", "heating_kw", "source"]

# ---------------- business + HouseZero (build_members.py) and civic + retail (build_civic.py) ----------------------
PARTS = os.path.join(OUT, "parts")
src_m = os.path.join(PARTS, "business_members.csv") if os.path.exists(os.path.join(PARTS, "business_members.csv")) else os.path.join(OUT, "members.csv")
src_l = os.path.join(PARTS, "business_members_load_2025_2026.parquet") if os.path.exists(os.path.join(PARTS, "business_members_load_2025_2026.parquet")) else os.path.join(OUT, "members_load_2025_2026.parquet")
BM = pd.read_csv(src_m, dtype={"zip": str})
BL = pd.read_parquet(src_l)
BM["group"] = np.where(BM.member_id == "hz_main", "housezero", "small_business")
BM.loc[BM.member_id == "hz_main", "building_type"] = "housezero"
BM["role"] = np.where(BM.group.eq("housezero") | BM.building_type.isin(["MediumOffice", "RetailStandalone"]), "prosumer", "flex")
BM["owner_kind"] = np.where(BM.group.eq("housezero"), "institution", "private")
BM["min_soc"] = 0.20; BM["cooling_center"] = False; BM["allow_building_modes"] = True
CM = pd.read_csv(os.path.join(OUT, "civic_members.csv"), dtype={"zip": str})
CL = pd.read_parquet(os.path.join(OUT, "civic_load.parquet"))

# ---------------- Boston Public Library, Central Library (measured) -------------------------------------------------
b = pd.read_csv(os.path.join(S, "bpl_5min_utc.csv"))
bs = pd.Series(pd.to_numeric(b.usage_kw, errors="coerce").values, index=pd.to_datetime(b.timestamp_utc, utc=True))
g = bs.resample("15min"); bpl = g.mean().where(g.count() >= 2).reindex(idx)
pk = float(np.nanmax(bpl))
LB = pd.DataFrame({"timestamp_utc": idx, "member_id": "bpl_central", "mode": "baseline", "demand_kw": bpl.values.astype("float32"),
                   "pv_kw": np.float32(0), "hvac_kw": np.nan, "cooling_kw": np.nan, "heating_kw": np.nan, "source": "measured"})
MB = pd.DataFrame([dict(member_id="bpl_central", source="measured", building_type="library_central", group="civic_measured",
                        role="prosumer", owner_kind="public", civic_role="Boston Public Library Central Library, 700 Boylston St (measured 5-min meter)",
                        sqft=676099, zip="02116", pv_kwdc=0.0, battery_kwh=round(2 * 0.30 * pk, 1), battery_kw=round(0.30 * pk, 1),
                        battery_label="HYPOTHETICAL: 2 h at 30% of measured peak kW", min_soc=0.30, cooling_center=True,
                        allow_building_modes=False, has_modes="baseline", tariff_id="ma_g2_example",
                        annual_kwh_2025_26=round(float(np.nansum(bpl)) / 4), peak_kw=round(pk, 1),
                        berdo_kwh_2025=8573524.8, coverage_pct=round(100 * float(bpl.notna().mean()), 1))])

# ---------------- homes (teammate's homesim, regenerated with its seed) ---------------------------------------------
H = os.path.join(S, "homesim/data/synthetic")
cal = json.load(open(os.path.join(H, "0.1.0-dev-representative-200/calibration.json")))["shape_vs_r1_nonhp"]["all"]
fac = np.array(cal["r1_shape"]) / np.array(cal["sim_shape"])          # soften the over-sharp evening peak toward R-1
hidx = pd.date_range(idx[0], idx[-1], freq="1h")

def homes(mode, community_n=None, messy=False):
    meta = pd.read_parquet(os.path.join(H, f"0.1.0-dev-{mode}-200/homes.parquet"))
    hh = pd.read_parquet(os.path.join(H, f"0.1.0-dev-{mode}-200/hourly"))
    hh["timestamp_utc"] = pd.to_datetime(hh.timestamp_utc, utc=True)
    if community_n:   # stratified: every battery / PV / heat-pump / EV home first, then random fill
        bat = meta[meta.battery_kwh > 0]                       # every battery home joins (they are the home prosumers)
        pri = meta[((meta.pv_kw_dc > 0) | (meta.heating_type == "heat_pump") | (meta.n_ev > 0)) & ~meta.index.isin(bat.index)]
        rest = meta.drop(bat.index).drop(pri.index)
        k = min(len(pri), community_n * 2 // 3 - len(bat))
        pick = pd.concat([bat, pri.sample(k, random_state=1), rest.sample(community_n - len(bat) - k, random_state=1)])
        meta = pick
    rows, mem = [], []
    zips = ["02132", "02131", "02136", "02124", "02122", "02130", "02126", "02129", "02127"]
    for _, m in meta.iterrows():
        x = hh[hh.home_id == m.home_id].set_index("timestamp_utc").reindex(hidx)
        loc_h = x.index.tz_convert(TZ).hour.values
        base_new = x.base_kw.values * fac[loc_h]
        base_new *= np.nansum(x.base_kw.values) / max(np.nansum(base_new), 1e-9)
        demand = x.total_load_kw.values - x.base_kw.values + base_new
        hvac = (x.heat_pump_kw.fillna(0) + x.backup_heat_kw.fillna(0) + x.ac_kw.fillna(0) + x.blower_kw.fillna(0)).values
        pv = x.pv_kw.fillna(0).values
        if messy:   # training-only copy: +-3% sensor noise and ~1.5% of hours missing in 2-48 h gaps
            demand = demand * (1 + rng.normal(0, 0.03, len(demand)))
            miss = np.zeros(len(demand), bool)
            while miss.mean() < 0.015:
                s0 = rng.integers(0, len(demand) - 48); miss[s0:s0 + rng.integers(2, 49)] = True
            demand = np.where(miss, np.nan, demand)
        mid = f"home_{m.home_id}" + ("_t" if messy else "")
        modes = ["baseline"]
        rows.append(pd.DataFrame({"timestamp_utc": hidx, "member_id": mid, "mode": "baseline", "demand_kw": demand.astype("float32"),
                                  "pv_kw": pv.astype("float32"), "hvac_kw": hvac.astype("float32"),
                                  "cooling_kw": x.ac_kw.values.astype("float32"), "heating_kw": (x.heat_pump_kw.fillna(0) + x.backup_heat_kw.fillna(0)).values.astype("float32"),
                                  "source": "synthetic_homesim"}))
        if m.n_ev > 0 and not messy:   # action: delay EV charging by 6 hours (after midnight); the energy comes back later
            ev = x.ev_kw.fillna(0).values
            ev_late = np.roll(ev, 6); ev_late[:6] = 0
            rows.append(rows[-1].assign(mode="ev_delay", demand_kw=(demand - ev + ev_late).astype("float32")))
            modes.append("ev_delay")
        has_bat = m.battery_kwh > 0
        mem.append(dict(member_id=mid, source="synthetic_homesim", building_type=f"home_{m.heating_type}", group="home",
                        role="prosumer" if has_bat else "flex", owner_kind="household", civic_role=f"single-family home ({m.home_type})",
                        sqft=float(m.sqft), zip=zips[len(mem) % len(zips)], pv_kwdc=float(m.pv_kw_dc),
                        battery_kwh=float(m.battery_kwh), battery_kw=float(m.battery_kw),
                        battery_label="from homesim" if has_bat else "", min_soc=float(m.battery_reserve_pct) / 100 if m.battery_reserve_pct > 1 else float(m.battery_reserve_pct),
                        cooling_center=False, allow_building_modes=bool(m.n_ev > 0), has_modes="|".join(modes), tariff_id="residential_flat",
                        annual_kwh_2025_26=round(float(np.nansum(demand))), peak_kw=round(float(np.nanmax(demand)), 2), n_ev=int(m.n_ev),
                        in_community=not messy))
    return pd.DataFrame(mem), pd.concat(rows, ignore_index=True)

HM, HL = homes("representative", community_n=40)
TM, TL = homes("balanced", messy=True)
print("homes community", len(HM), HM.role.value_counts().to_dict(), "| training-only", len(TM))

# ---------------- combine ----------------------------------------------------------------------------------------
M = pd.concat([BM, CM, MB, HM, TM], ignore_index=True)
M["in_community"] = M["in_community"].fillna(True).astype(bool)
L = pd.concat([BL[cols] if "hvac_kw" in BL else BL.assign(hvac_kw=np.nan)[cols], CL[cols], LB[cols], HL[cols], TL[cols]], ignore_index=True)
for c in ("member_id", "mode", "source"):
    L[c] = L[c].astype(str).astype("category")
for c in ("demand_kw", "pv_kw", "hvac_kw", "cooling_kw", "heating_kw"):
    L[c] = L[c].astype("float32")
check_window(L.timestamp_utc)
os.makedirs(os.path.join(OUT, "parts"), exist_ok=True)
for f in ("members.csv", "members_load_2025_2026.parquet"):
    if not os.path.exists(os.path.join(PARTS, "business_" + f)):
        os.replace(os.path.join(OUT, f), os.path.join(PARTS, "business_" + f))
M.to_csv(os.path.join(OUT, "members.csv"), index=False)
L.to_parquet(os.path.join(OUT, "members_load_2025_2026.parquet"), compression="zstd", index=False)
print(M.groupby(["group", "in_community"]).size().to_string())
print("rows", len(L), "| period", L.timestamp_utc.min(), L.timestamp_utc.max())
