"""Scale the simulated community across Boston with the BERDO 2026 (2025 data) building stock.

For each archetype we measure, from the simulated day, peak kW avoided and dollars saved per 1,000 sq ft.
A zip's projection = its floor area of that archetype x adoption x per-sq-ft effect. This is a projection, not a
prediction for any specific building. BERDO covers buildings of 20,000 sq ft or more; apartments are excluded
because no member represents them.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ARCHETYPE = {"SmallOffice": "office", "MediumOffice": "office", "RetailStandalone": "retail", "RetailStripmall": "retail",
             "FullServiceRestaurant": "restaurant", "QuickServiceRestaurant": "restaurant", "housezero": "office",
             "library_central": "library"}
CIVIC = ["school", "library", "community_center", "fire_station", "police_station", "museum", "courthouse_office",
         "enclosed_mall", "large_retail", "supermarket", "strip_mall"]
ARCHETYPE.update({c: c for c in CIVIC})
ADOPTION = [0.0, 0.1, 0.2, 0.3, 0.5]


def per_sqft_effects(day: dict) -> pd.DataFrame:
    need = [i for i, s in enumerate(day["grid"]["signal"]) if s == "use_less"]
    rows = []
    for mid, m in day["members"].items():
        if not m["sqft"] or str(m["building_type"]).startswith("home_"):
            continue   # homes are excluded from the Boston projection (BERDO has no single-family homes)
        nb = np.asarray(m["strategies"]["no_battery"]["import_kw"])
        co = np.asarray(m["strategies"]["collective"]["import_kw"])
        hrs = need or list(range(len(nb)))
        rows.append({"member": mid, "archetype": ARCHETYPE.get(m["building_type"], "other_commercial"),
                     "sqft": m["sqft"],
                     "need_kw_avoided": float(np.mean(nb[hrs] - co[hrs])),
                     "peak_kw_avoided": float(nb.max() - co.max()),
                     "usd_saved": m["bills"]["no_battery"]["total_usd"] - m["bills"]["collective"]["total_usd"]})
    df = pd.DataFrame(rows)
    g = df.groupby("archetype")[["need_kw_avoided", "peak_kw_avoided", "usd_saved", "sqft"]].sum()
    eff = pd.DataFrame({"need_kw_per_ksf": g["need_kw_avoided"] / g["sqft"] * 1000,
                        "peak_kw_per_ksf": g["peak_kw_avoided"] / g["sqft"] * 1000,
                        "usd_per_ksf_day": g["usd_saved"] / g["sqft"] * 1000})
    eff.loc["other_commercial"] = eff.mean()
    return eff


def project(stock: pd.DataFrame, eff: pd.DataFrame) -> dict:
    s = stock[stock["archetype"] != "residential_multifamily"].copy()
    s["zip"] = s["zip"].astype(str).str.zfill(5)
    out = {"adoption": ADOPTION, "zips": {}, "citywide": {}}
    for a in ADOPTION:
        tot_kw = tot_usd = 0.0
        for z, grp in s.groupby("zip"):
            kw = usd = 0.0
            for _, r in grp.iterrows():
                e = eff.loc[r["archetype"]] if r["archetype"] in eff.index else eff.loc["other_commercial"]
                kw += r["total_gfa_sqft"] / 1000 * a * e["need_kw_per_ksf"]
                usd += r["total_gfa_sqft"] / 1000 * a * e["usd_per_ksf_day"]
            d = out["zips"].setdefault(z, {"buildings": int(grp["n_buildings"].sum()), "gfa_sqft": float(grp["total_gfa_sqft"].sum()),
                                           "kw": [], "usd_day": []})
            d["kw"].append(round(kw, 1)); d["usd_day"].append(round(usd, 0))
            tot_kw += kw; tot_usd += usd
        out["citywide"][str(a)] = {"mw_avoided": round(tot_kw / 1000, 2), "usd_day": round(tot_usd, 0)}
    out["covered_buildings"] = int(s["n_buildings"].sum())
    out["covered_gfa_sqft"] = float(s["total_gfa_sqft"].sum())
    out["effects_per_1000_sqft"] = eff.round(4).reset_index().rename(columns={"index": "archetype"}).to_dict("records")
    return out
