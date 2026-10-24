"""BERDO 2026 disclosure (2025 calendar-year data) -> clean building table + zip x archetype stock + medians."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import json
src = os.path.join(S, "berdo/berdo2026.xlsx")
x = pd.read_excel(src, sheet_name="Buildings & Campuses", dtype={"BERDO ID": str, "Building Address Zip Code": str})
keep = {"BERDO ID": "berdo_id", "Building Address": "address", "Building Address Zip Code": "zip",
        "Gross Floor Area (sq ft)": "gfa_sqft", "Largest Property Type": "largest_property_type",
        "Electricity Usage (kWh)": "elec_kwh_2025", "Total Site Energy Usage (kBtu)": "site_energy_kbtu_2025",
        "Natural Gas Usage (kBtu)": "gas_kbtu_2025", "Energy Star Score": "energy_star_score",
        "Site EUI (Energy Use Intensity kBtu/ft²)": "site_eui_kbtu_sqft", "Reporting Compliance Status": "reporting_status"}
b = x[list(keep)].rename(columns=keep)   # Parcel Owner Name and all other columns dropped
b["zip"] = b.zip.str.extract(r"(\d{5})")[0].fillna(b.zip.str.zfill(5))
for c in ["gfa_sqft","elec_kwh_2025","site_energy_kbtu_2025","gas_kbtu_2025","energy_star_score","site_eui_kbtu_sqft"]:
    b[c] = pd.to_numeric(b[c], errors="coerce")
pt = b.largest_property_type.fillna("")
RETAIL = {"Retail Store","Strip Mall","Supermarket/Grocery Store"}
REST = {"Restaurant","Food Service","Fast Food Restaurant","Other - Restaurant/Bar"}
b["archetype"] = np.select(
    [pt.eq("Office"), pt.isin(RETAIL), pt.isin(REST), pt.eq("K-12 School"), pt.eq("Multifamily Housing"), pt.eq("")],
    ["office", "retail", "restaurant", "school", "residential_multifamily", "unknown"], "other_commercial")
b["office_size"] = np.where(b.archetype.eq("office"), np.where(b.gfa_sqft < 25000, "SmallOffice", "MediumOffice"), "")
b["covered_by_archetypes"] = b.archetype.isin(["office","retail","restaurant","school","residential_multifamily"])
b["elec_kwh_per_sqft_2025"] = b.elec_kwh_2025 / b.gfa_sqft
ok = b.elec_kwh_per_sqft_2025.between(0.2, 200)
b.loc[~ok, "elec_kwh_per_sqft_2025"] = np.nan
b.to_csv(os.path.join(OUT, "berdo_buildings_clean.csv"), index=False)
g = b.groupby(["zip","archetype"])
st = pd.DataFrame({"n_buildings": g.size(), "total_gfa_sqft": g.gfa_sqft.sum(),
                   "n_with_elec": g.elec_kwh_2025.count(), "total_elec_kwh_2025": g.elec_kwh_2025.sum(min_count=1),
                   "gfa_sqft_with_elec": b[b.elec_kwh_2025.notna()].groupby(["zip","archetype"]).gfa_sqft.sum()}).reset_index()
st["elec_kwh_per_sqft_2025"] = st.total_elec_kwh_2025 / st.gfa_sqft_with_elec
st.to_csv(os.path.join(OUT, "boston_stock.csv"), index=False)
med = b[ok].groupby("archetype").elec_kwh_per_sqft_2025.agg(["median","count", lambda s: s.quantile(.25), lambda s: s.quantile(.75)])
med.columns = ["median_kwh_sqft","n","p25","p75"]
med.round(3).to_csv(os.path.join(OUT, "berdo_archetype_medians.csv"))
off = st[st.archetype=="office"].sort_values("total_elec_kwh_2025", ascending=False).head(8)
rep = {"rows": len(b), "with_elec": int(b.elec_kwh_2025.notna().sum()), "archetype_counts": b.archetype.value_counts().to_dict(),
       "medians": med.round(2).reset_index().to_dict("records"),
       "top_office_zips": off[["zip","n_buildings","total_elec_kwh_2025"]].to_dict("records")}
json.dump(rep, open(os.path.join(S,"unified_build/_stock_report.json"),"w"), indent=1, default=str); print(json.dumps(rep, indent=1, default=str))
