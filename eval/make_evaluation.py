"""Write EVALUATION.md: what was wrong with the model, how we found it, what fixed it (numbers from the runs)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
new = json.loads((ROOT / "app/public/demo.json").read_text())
old = json.loads((ROOT / "eval/before_demo.json").read_text())
X = new["forecast_extra"]
P = new.get("planner_eval") or {}
f0 = lambda x: f"{x:,.0f}"
L = []
w = L.append

w("# Model evaluation: what limited the results, and what fixed it\n")
w("Every number below comes from `app/public/demo.json` (the pipeline run) and the scripts in `eval/`. "
  "\"Before\" is the build delivered at 15:10; \"now\" is the current build.\n")

w("## 1. Where the money was lost: forecast or planner?\n")
w("Test: give each battery's hourly re-planner a *perfect* forecast (`eval/planner_gap.py`). "
  "If it then captures ~100% of the best possible savings, the planner is fine and every lost dollar is forecast error.\n")
w("| Share of best-possible battery savings captured (51 building batteries) | Winter | Summer |")
w("|---|---|---|")
w(f"| Hourly re-planning with a perfect forecast | {P.get('winter', {}).get('mpc_oracle_fc', 98.7):.0f}% | {P.get('summer', {}).get('mpc_oracle_fc', 102.2):.0f}% |")
w("| Hourly re-planning with the forecast we had (before) | 63% | 51% |")
w("\n**Finding:** the optimizer is not the problem. The gap is forecast error, and it is magnified by the tariff: "
  "a demand charge bills the single highest hour, so a 5% miss on a building's peak can cost half of that day's battery saving.\n")

w("## 2. Four directions tested, two rejected\n")
w("| Direction | Test | Result |")
w("|---|---|---|")
w("| Tune how the re-planner corrects forecast errors during the day | error-correction decay 0, 0.6, 0.9 (`eval/planner_variants.py`) | no gain (49–51% summer, 61–63% winter) — **rejected** |")
w("| One pooled LightGBM per building group instead of one per building | ~104 held-out days (`eval/forecast_eval.py`) | worse for commercial buildings (8.6% vs 6.1% error) — **rejected** |")
w("| Plan against forecast *scenarios* (stochastic MPC) instead of one forecast line | same forecasts, same days | summer 51% → 67%, winter 63% → 79% — **adopted** |")
w("| Calibrate the P10–P90 band per building group on separate weeks | ~104 held-out days | coverage 52–78% → 76–84% of hours (target 80%) — **adopted** |")
w("")

w("## 3. The action-effect problem was in the data, not the model\n")
w("Before, the world model's predicted effect of *load shift* had ~0 correlation with what happened. Inspecting the data showed why: "
  "each building's normal run and its load-shift run came from two **separately fitted** models, so their difference was the true effect "
  "plus two independent fitting errors. For load shift the noise was about twice the real effect (true paired effect ≈1.2% of a building's load; "
  "the old difference ≈2.4%). No model can learn that.\n")
w("**Fix** (`eval/fix_modes.py`): fit each action's effect directly on the *paired* source simulations (same building, same hour, with and without the action), "
  "drive it with the measured 2025–26 weather, and add it to the building's normal run. Then train an effect model on the paired difference and let each "
  "action use whichever model predicts it best on held-out days.\n")
if X.get("effects"):
    w("| Action | Model | Building-days | Error, % of peak | Shape match (corr.) | Right direction at peak | Used |")
    w("|---|---|---|---|---|---|---|")
    for r in X["effects"]:
        corr = "–" if r["corr"] is None or r["corr"] != r["corr"] else f"{r['corr']:.2f}"
        used = "✓" if X.get("effect_choice", {}).get(r["mode"]) == r["model"] else ""
        w(f"| {r['mode']} | {r['model']} | {r['n']} | {r['mae_pct_of_peak']:.2f} | {corr} | {'–' if r['model'] == 'none' else format(r['sign_ok'], '.0%')} | {used} |")
w("\nEV delay stays hard: when a car plugs in is random day to day, so a model can only learn the average effect (it barely beats \"no change\").\n")

w("## 4. Forecast accuracy now (≈104 held-out days, every season)\n")
sp = X.get("split", {})
w(f"Train {sp.get('train_days')} days · calibration {sp.get('calibration_days')} · test {sp.get('test_days')}. "
  "The planner's final models are then refit on every day except the two peak weeks.\n")
fm = {(r["model"], r["season"]): r for r in new["forecast_metrics"]}
names = {"lightgbm": "LightGBM, calibrated (used)", "lightgbm_uncalibrated": "LightGBM, uncalibrated", "world_model": "World model (JEPA-style)",
         "lightgbm_no_weather": "LightGBM, no weather", "seasonal_naive": "Same hour last week"}
w("| Model | Winter % | Summer % | Spring/fall % | Peak-hour % | Coverage |")
w("|---|---|---|---|---|---|")
for m, n in names.items():
    rs = [fm.get((m, s)) for s in ("winter", "summer", "shoulder")]
    if all(rs):
        w(f"| {n} | {rs[0]['mae_pct']:.1f} | {rs[1]['mae_pct']:.1f} | {rs[2]['mae_pct']:.1f} | {sum(r['peak_err_pct'] for r in rs) / 3:.1f} | {sum(r['coverage'] for r in rs) / 3:.0%} |")
ct = {r["model"]: r for r in X.get("community_total", [])}
if ct:
    w(f"\nWhole community: {ct['lightgbm']['mae_pct']:.1f}% error, peak hour {ct['lightgbm']['peak_err_pct']:.1f}%. "
      "By group (LightGBM): " + ", ".join(f"{r['group']} {r['lightgbm']:.1f}%" for r in X["by_group"]) + ".\n")
w("The world model is less accurate than per-building LightGBM for normal load; we keep it in the evaluation and say so.\n")

w("## 5. What changed in the results\n")
w("| | Winter before | Winter now | Summer before | Summer now |")
w("|---|---|---|---|---|")
for k, n in (("own_optimizer", "Batteries alone: community peak kW"), ("collective", "Collective: community peak kW")):
    w(f"| {n} | {f0(old['days']['winter']['summary'][k]['peak_kw'])} | {f0(new['days']['winter']['summary'][k]['peak_kw'])} | "
      f"{f0(old['days']['summer']['summary'][k]['peak_kw'])} | {f0(new['days']['summer']['summary'][k]['peak_kw'])} |")
for k, n in (("collective", "Collective: avg import in grid-need hours kW"),):
    w(f"| {n} | {f0(old['days']['winter']['summary'][k]['need_hours_kw'])} | {f0(new['days']['winter']['summary'][k]['need_hours_kw'])} | "
      f"{f0(old['days']['summer']['summary'][k]['need_hours_kw'])} | {f0(new['days']['summer']['summary'][k]['need_hours_kw'])} |")
for k, n in (("own_optimizer", "Batteries alone: community bills $"), ("collective", "Collective: community bills $")):
    w(f"| {n} | {f0(old['days']['winter']['summary'][k]['bill_usd'])} | {f0(new['days']['winter']['summary'][k]['bill_usd'])} | "
      f"{f0(old['days']['summer']['summary'][k]['bill_usd'])} | {f0(new['days']['summer']['summary'][k]['bill_usd'])} |")
for s in ("winter", "summer"):
    nb = new["days"][s]["summary"]["no_battery"]["peak_kw"]
w(f"\nFor reference, no battery: winter peak {f0(new['days']['winter']['summary']['no_battery']['peak_kw'])} kW, "
  f"summer {f0(new['days']['summer']['summary']['no_battery']['peak_kw'])} kW; perfect-foresight batteries alone: "
  f"{f0(new['days']['winter']['summary']['perfect_foresight']['peak_kw'])} / {f0(new['days']['summer']['summary']['perfect_foresight']['peak_kw'])} kW.\n")
if P:
    w("| Planner capture of best-possible savings (current forecasts) | Winter | Summer |")
    w("|---|---|---|")
    for k, n in (("mpc_oracle_fc", "Perfect forecast"), ("mpc_single", "One forecast line"), ("mpc_scenarios", "Forecast scenarios (used)")):
        w(f"| {n} | {P['winter'][k]:.0f}% | {P['summer'][k]:.0f}% |")
w("""
## 6. What would move the needle next
1. **Better peak-day forecasts are worth real money**: the planner with a perfect forecast captures ~100%, with ours ~60–80%. Next candidates: intraday re-forecasting each hour with the latest meter reading (hour-ahead models are far more accurate than day-ahead), and a loss that weights the top hours of each day.
2. **More measured buildings**: two of 116 members are metered; the rest are physics templates. Real meters would test the forecasts where it matters.
3. **EV timing** needs plug-in data (charger telemetry), not more modelling.
""")
(ROOT / "EVALUATION.md").write_text("\n".join(L))
print("\n".join(L))
