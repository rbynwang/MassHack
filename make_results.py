"""Write RESULTS.md from app/public/demo.json (run after run_all.py)."""
import json
import sys
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else "app/public/demo.json")
d = json.loads(src.read_text())
L = []
w = L.append
f0 = lambda x: f"{x:,.0f}"

w("# Results (generated from app/public/demo.json by make_results.py)\n")
w(f"Period: {d['period']}. Planner forecaster: **{d['forecaster_used']}**. "
  f"Community: {len(d['members_table'])} members; the world model also trained on "
  f"{d['forecast_extra'].get('train_members', '?')} buildings including 200 training-only homes.\n")

X = d["forecast_extra"]
sp = X.get("split", {})
w(f"## Forecast accuracy on held-out days (day-ahead, noisy weather forecast, no future data)\n")
w(f"Split by whole weeks: train {sp.get('train_days')} days · band calibration {sp.get('calibration_days')} days · "
  f"test {sp.get('test_days')} days (one week in every month plus the week around each peak day).\n")
names = {"world_model": "World model (JEPA-style, calibrated)", "lightgbm": "LightGBM with weather (calibrated)",
         "lightgbm_uncalibrated": "LightGBM, uncalibrated band", "lightgbm_no_weather": "LightGBM without weather", "seasonal_naive": "Same hour last week"}
fm = {(r["model"], r["season"]): r for r in d["forecast_metrics"]}
w("| Model | Winter error % | Summer error % | Spring/fall error % | Peak-hour error % | P10–P90 coverage (target 80%) |")
w("|---|---|---|---|---|---|")
for m, n in names.items():
    rs = [fm[(m, se)] for se in ("winter", "summer", "shoulder") if (m, se) in fm]
    if len(rs) == 3:
        w(f"| {n} | {rs[0]['mae_pct']:.1f} | {rs[1]['mae_pct']:.1f} | {rs[2]['mae_pct']:.1f} | "
          f"{sum(r.get('peak_err_pct', 0) for r in rs) / 3:.1f} | {sum(r['coverage'] for r in rs) / 3:.0%} |")
ct = {r["model"]: r for r in X.get("community_total", [])}
if ct:
    w(f"\nWhole community (sum of all members): LightGBM {ct['lightgbm']['mae_pct']:.1f}% error, peak hour {ct['lightgbm']['peak_err_pct']:.1f}%; "
      f"world model {ct['world_model']['mae_pct']:.1f}% / {ct['world_model']['peak_err_pct']:.1f}%.")
w("\nPer-member error averages every member equally, so the 40 noisy single homes pull it up.\n")
w("### By building group (both seasons)\n")
w("| Group | World model % | LightGBM % | LightGBM no weather % | Last week % |")
w("|---|---|---|---|---|")
for r in d["forecast_extra"]["by_group"]:
    w(f"| {r['group']} | {r['world_model']:.1f} | {r['lightgbm']:.1f} | {r['lightgbm_no_weather']:.1f} | {r['seasonal_naive']:.1f} |")
hc = d["forecast_extra"].get("homes_combined", {})
if hc:
    w(f"\n40 homes forecast together (their sum): LightGBM {hc['lightgbm']:.1f}% · world model {hc['world_model']:.1f}%.\n")

if X.get("effects"):
    w("## Action effects: does the model know what a building mode does? (held-out days)\n")
    w("| Action | Model | Building-days | Error, % of building peak | Shape match (median corr.) | Right direction at peak hour | Predicted / actual kW at peak, summed |")
    w("|---|---|---|---|---|---|---|")
    for r in X["effects"]:
        used = " (used)" if X.get("effect_choice", {}).get(r["mode"]) == r["model"] else ""
        corr = "–" if r["corr"] is None or r["corr"] != r["corr"] else f"{r['corr']:.2f}"
        sg = "–" if r["model"] == "none" else f"{r['sign_ok']:.0%}"
        w(f"| {r['mode']} | {r['model']}{used} | {r['n']} | {r['mae_pct_of_peak']:.2f} | {corr} | {sg} | {f0(r['pred_kw_at_peak'])} / {f0(r['act_kw_at_peak'])} |")
    w("")
P = d.get("planner_eval")
if P:
    w("## Does forecasting turn into savings? (prosumer batteries, both peak days)\n")
    w("Share of the best possible battery savings (perfect knowledge of the day) captured, same forecasts:\n")
    w("| Planner | Winter | Summer |"); w("|---|---|---|")
    for k, n in (("mpc_oracle_fc", "Hourly re-planning with a perfect forecast"), ("mpc_single", "Hourly re-planning on one forecast line (before)"),
                 ("mpc_scenarios", "Hourly re-planning over forecast scenarios (now)")):
        w(f"| {n} | {P['winter'][k]:.0f}% | {P['summer'][k]:.0f}% |")
    w("")
w("### The two measured buildings\n")
w("| Building | Season | LightGBM % | No weather % | Last week % | World model % |")
w("|---|---|---|---|---|---|")
rb = {}
for r in d["forecast_extra"]["real_buildings"]:
    rb.setdefault((r["member"], r["season"]), {})[r["model"]] = r["mae_pct"]
lab = {"bpl_central": "Boston Public Library Central", "hz_main": "HouseZero (Harvard)"}
for (mid, se), v in sorted(rb.items()):
    w(f"| {lab.get(mid, mid)} | {se} | {v.get('lightgbm', 0):.1f} | {v.get('lightgbm_no_weather', 0):.1f} | "
      f"{v.get('seasonal_naive', 0):.1f} | {v.get('world_model', 0):.1f} |")
w("")

strat = {"no_battery": "No battery", "vendor_default": "Vendor default battery", "own_optimizer": "Each battery optimizing alone (hourly re-planning)",
         "collective": "Collective", "perfect_foresight": "Perfect foresight, each alone (ceiling)"}
for season in ("winter", "summer"):
    x = d["days"][season]
    s = x["summary"]
    pay = sum(x["payouts_usd"].values())
    need = [i for i, g in enumerate(x["grid"]["signal"]) if g == "use_less"]
    cr = x["coordination_round"]
    w(f"## {season.title()} peak day: {x['date']}\n")
    w(f"Grid-need hours: {len(need)} · heat warning: {'yes' if x['heat_warning'] else 'no'} · signed receipts: {len(x['receipts'])} · "
      f"commands refused by the trust layer: {len(x['refused_commands'])} (includes one deliberate oversized test request per hour) · "
      f"paid out to members: ${pay:,.2f}\n")
    w(f"Coordination round: planned community peak {f0(max(cr['community_plan_round1_kw']))} → {f0(max(cr['community_plan_round2_kw']))} kW.\n")
    w("| Strategy | Community peak kW | Avg import in grid-need hours kW | Bills $ | Net of payouts $ |")
    w("|---|---|---|---|---|")
    for k, n in strat.items():
        net = s[k]["bill_usd"] - (pay if k == "collective" else 0)
        w(f"| {n} | {f0(s[k]['peak_kw'])} | {f0(s[k]['need_hours_kw'])} | {f0(s[k]['bill_usd'])} | {f0(net)} |")
    nb, co, so = s["no_battery"], s["collective"], s["own_optimizer"]
    w(f"\nCollective vs no battery: grid-need-hour import −{(1 - co['need_hours_kw'] / nb['need_hours_kw']):.1%}, "
      f"community peak −{(1 - co['peak_kw'] / nb['peak_kw']):.1%}. "
      f"Collective vs each battery alone: grid-need-hour import −{(1 - co['need_hours_kw'] / so['need_hours_kw']):.1%}, "
      f"community peak {co['peak_kw'] / so['peak_kw'] - 1:+.1%}.\n")

w("## What if tomorrow is hotter? (summer peak day, plan only)\n")
w("| Forecast shift | Forecast high °C | Heat warning | Planned peak solo kW | Planned peak coordinated kW | kW assigned in grid-need hours |")
w("|---|---|---|---|---|---|")
for k in sorted(d["whatif"], key=float):
    v = d["whatif"][k]
    r1, r2 = max(v["planned_round1_kw"]), max(v["planned_round2_kw"])
    acc = sum(v["accepted_kw_by_source"].values())
    w(f"| {float(k):+.0f} °C | {max(v['temp_forecast_c']):.1f} | {'yes' if v['heat_warning'] else 'no'} | {f0(r1)} | {f0(r2)} | {f0(acc)} |")
w("\nWith a heat warning, cooling centers (libraries, community centers, BPL Central) hold 50% battery and refuse building modes; fire and police always hold 80%; museums offer battery only.\n")

w("## Boston projection (BERDO 2025 stock, buildings ≥ 20,000 sq ft, apartments and homes excluded)\n")
w("| Adoption | Winter MW avoided | Winter $/day | Summer MW avoided | Summer $/day |")
w("|---|---|---|---|---|")
b = d["boston"]
for a in b["winter"]["citywide"]:
    wi, su = b["winter"]["citywide"][a], b["summer"]["citywide"][a]
    w(f"| {float(a):.0%} | {wi['mw_avoided']:.2f} | {f0(wi['usd_day'])} | {su['mw_avoided']:.2f} | {f0(su['usd_day'])} |")

w("""
## Honest caveats
- Measured buildings: HouseZero and BPL Central. Civic, retail and business members are NREL ComStock building designs driven by measured 2025–26 HouseZero weather; homes are synthetic (homesim, seed 42).
- On the single highest hour, the collective is below batteries acting alone in summer and about 1% above in winter: members give up a little of their own peak shaving to deliver in the grid-need hours, where the collective beats every realistic strategy.
- Batteries for civic/business members are hypothetical (2 h at 30% of peak); flex costs and demand-response pay are assumptions labeled in code.
- One tariff (Concord MA G-2) stands in for Eversource G-2; the demand charge is billed on each simulated day's peak. Bills are single peak days, not annualized.
- The HouseZero rooftop sensor reads hotter than the airport on sunny afternoons; it is still the only weather source by the team's data rule.
""")
Path("RESULTS.md").write_text("\n".join(L))
print("\n".join(L))
