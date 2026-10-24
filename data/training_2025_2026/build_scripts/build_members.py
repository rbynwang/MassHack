"""members.csv + members_load_2025_2026.parquet (hz_main measured + 40 template members driven by HZ weather)."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import json, shutil
wx = pd.read_parquet(os.path.join(OUT, "weather.parquet")); grid = pd.read_parquet(os.path.join(OUT, "grid.parquet"))
hz = pd.read_parquet(os.path.join(S, "hz_out/hz_15min_model.parquet"))
bl = pd.read_csv(os.path.join(S, "datapack/buildings.csv")).set_index("bldg_id")
biz = pd.read_parquet(os.path.join(S, "unified_build/_business_load.parquet"))
med = pd.read_csv(os.path.join(OUT, "berdo_archetype_medians.csv")).set_index("archetype").median_kwh_sqft
dr = pd.read_csv(os.path.join(OUT, "dr_events_2025.csv"))
ts = wx.timestamp_utc; n = len(ts); ppk = wx.pv_per_kwdc.values

# ---------------- hz_main (measured) + rule-based flex modes
hvac = (hz.heat_pump_kw.fillna(0) + hz.pumps_kw.fillna(0)).values
dem = hz.building_demand_kw.values
slab = pd.Series(hz.slab_temp_mean_c.values); d2 = (slab.shift(-8) - slab).abs()
evid = dict(slab_abs_change_2h_median_c=round(float(d2.median()),3), slab_abs_change_2h_p95_c=round(float(d2.quantile(.95)),3),
            indoor_temp_p05_p95_c=[round(float(hz.indoor_temp_mean_c.quantile(q)),2) for q in (.05,.95)],
            hvac_kw_p95=round(float(np.nanpercentile(hvac,95)),2), hvac_kw_max=round(float(np.nanmax(hvac)),2))
cap = evid["hvac_kw_p95"]
pre = np.zeros(n); cur = np.zeros(n)
tsi = pd.DatetimeIndex(ts)
for _, r in dr.iterrows():
    s0 = tsi.get_loc(pd.Timestamp(r.start_utc)); s1 = tsi.get_loc(pd.Timestamp(r.end_utc)) if pd.Timestamp(r.end_utc) in tsi else n
    # thermal_preheat: move up to 50% of in-window HVAC kWh into the 2 h (8 steps) before the window,
    # bounded so pre-window HVAC never exceeds HouseZero's own p95 HVAC kW (TABS slab coasts ~2 h; see evidence)
    win = slice(s0, s1); prew = slice(max(s0-8,0), s0)
    e_want = 0.5*hvac[win].sum()
    room = np.clip(cap - hvac[prew], 0, None); e_room = room.sum()
    e = min(e_want, e_room)
    if e > 0 and hvac[win].sum() > 0:
        pre[prew] += room * (e/e_room); pre[win] -= hvac[win] * (e/hvac[win].sum())
    # hvac_curtail: -20% HVAC for the first <=2 h of the window, equal-energy rebound spread over the next 2 h
    c = slice(s0, min(s0+8, s1)); red = 0.2*hvac[c]; cur[c] -= red
    rb = slice(c.stop, min(c.stop+8, n)); cur[rb] += red.sum()/max(rb.stop-rb.start,1)
rows = []
def add(mid, mode, demand, pv, src, cool=None, heat=None, hv=None):
    rows.append(pd.DataFrame({"timestamp_utc": ts, "member_id": mid, "mode": mode, "demand_kw": np.asarray(demand, "float32"),
        "pv_kw": np.asarray(pv, "float32"), "hvac_kw": None if hv is None else np.asarray(hv,"float32"),
        "cooling_kw": None if cool is None else np.asarray(cool,"float32"), "heating_kw": None if heat is None else np.asarray(heat,"float32"),
        "source": src}))
add("hz_main", "baseline", dem, hz.pv_kw.values, "measured", hv=hvac)
add("hz_main", "thermal_preheat", dem + pre, hz.pv_kw.values, "measured_plus_rule_based_flex", hv=hvac + pre)
add("hz_main", "hvac_curtail", dem + cur, hz.pv_kw.values, "measured_plus_rule_based_flex", hv=hvac + cur)
hz_ann = np.nansum(dem)/4; hz_peak = float(np.nanmax(dem))
hz_kwdc_equiv = float(np.nansum(hz.pv_kw)/np.nansum(ppk))
members = [dict(member_id="hz_main", source="measured", building_type="HouseZero (small net-positive office, Cambridge)",
    berdo_archetype="office", sqft=17000, sqft_note="approx. public figure for HouseZero; not in dataset", zip="02138",
    pv_kwdc=round(hz_kwdc_equiv,1), pv_note="measured PV; kWdc = energy-equivalent of pvlib model (true nameplate not in data)",
    battery_kwh=13.5, battery_kw=5.0, battery_label="HYPOTHETICAL home-style battery (HouseZero has none in data)",
    tariff_id="TBD_verify", has_modes="baseline|thermal_preheat|hvac_curtail",
    annual_kwh_2025_26=round(hz_ann,0), peak_kw=round(hz_peak,2))]
# ---------------- 40 template members
ARCH = {"SmallOffice":"office","MediumOffice":"office","RetailStandalone":"retail","RetailStripmall":"retail","FullServiceRestaurant":"restaurant"}
for mid, g in biz.groupby("member_id", observed=True):
    b = int(mid.split("_")[1]); kwdc = float(bl.pv_kwdc_equiv_pvlib[b]); pv = ppk * kwdc
    modes = list(g["mode"].unique())
    for mode, gm in g.groupby("mode", observed=True):
        gm = gm.sort_values("timestamp_utc")
        add(mid, mode, gm.demand_kw.values, pv, "simulated_template_hz_weather", cool=gm.cooling_kw.values, heat=gm.heating_kw.values,
            hv=gm.cooling_kw.values + gm.heating_kw.values)
    base = g[g["mode"]=="baseline"]; ann = base.demand_kw.sum()/4; pk = float(base.demand_kw.max())
    a = ARCH[bl.building_type[b]]; kps = ann/bl.sqft[b]
    members.append(dict(member_id=mid, source="simulated_template_hz_weather", building_type=bl.building_type[b], berdo_archetype=a,
        sqft=float(bl.sqft[b]), sqft_note="ComStock template floor area", zip="", pv_kwdc=kwdc,
        pv_note="pv_kw = weather.pv_per_kwdc x pv_kwdc (rooftop 40% coverage sizing)",
        battery_kwh=round(2*0.25*pk,1), battery_kw=round(0.25*pk,1), battery_label="HYPOTHETICAL default: 2 h at 25% of annual peak kW",
        tariff_id="ma_g2_example", has_modes="|".join(["baseline"] + [m for m in ("load_shift_33","precool_42") if m in modes]),
        annual_kwh_2025_26=round(ann,0), peak_kw=round(pk,2)))
M = pd.DataFrame(members)
M["kwh_per_sqft_2025_26"] = (M.annual_kwh_2025_26/M.sqft).round(2)
M["berdo_median_kwh_per_sqft_2025"] = M.berdo_archetype.map(med).round(2)
M["scale_to_berdo"] = (M.berdo_median_kwh_per_sqft_2025/M.kwh_per_sqft_2025_26).round(3)
M.to_csv(os.path.join(OUT, "members.csv"), index=False)
L = pd.concat(rows, ignore_index=True)
for c in ("member_id","mode","source"): L[c] = L[c].astype("category")
check_window(L.timestamp_utc)
L.to_parquet(os.path.join(OUT, "members_load_2025_2026.parquet"), compression="zstd", index=False)
shutil.copy(os.path.join(S, "datapack/tariff.json"), os.path.join(OUT, "tariff.json"))
cmp = M[M.source!="measured"].groupby("building_type").agg(n=("member_id","size"), kwh_sqft_median=("kwh_per_sqft_2025_26","median"),
        berdo_median=("berdo_median_kwh_per_sqft_2025","first"), scale_median=("scale_to_berdo","median")).round(3)
rep = dict(hz_flex_evidence=evid, hz_preheat_shifted_kwh=round(float(pre[pre>0].sum()/4),2), hz_curtail_kwh=round(float(-cur[cur<0].sum()/4),2),
           rows=len(L), members=len(M), kwh_sqft_vs_berdo=cmp.reset_index().to_dict("records"), hz_annual_kwh=round(hz_ann,0), hz_pv_kwdc_equiv=round(hz_kwdc_equiv,2))
json.dump(rep, open(os.path.join(S,"unified_build/_members_report.json"),"w"), indent=1, default=str); print(json.dumps(rep, indent=1, default=str))
