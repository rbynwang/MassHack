"""Experiment 2: planner variants on the SAME forecasts. Which decision rule recovers the savings?"""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "eval"))
DATA = os.environ.get("MASSHACK_DATA", str(ROOT / "data" / "model_inputs"))
import sys, pickle, numpy as np, pandas as pd
from pathlib import Path
from masshack.data import Dataset
from masshack.physics import Tariff, bill, simulate_schedule
from masshack.agents import build_agents
from masshack.optimizer import optimize_battery, mpc_realize, mpc_realize_robust
ds = Dataset(DATA); tariff = Tariff.from_json(Path(DATA) / "tariff.json"); agents = build_agents(ds, tariff)
C = pickle.load(open(sys.argv[1] if len(sys.argv) > 1 else "app/forecast_cache.pkl", "rb"))["fc"]
peaks = ds.pick_peak_days(); rows = []
V = {
  "mpc_oracle_fc": lambda la, pv, f, a: mpc_realize(la, pv, la, a.battery, a.tariff),
  "mpc_single": lambda la, pv, f, a: mpc_realize(la, pv, np.maximum(f.p50.values, 0.9 * f.p90.values), a.battery, a.tariff),
  "mpc_scenarios": lambda la, pv, f, a: mpc_realize_robust(la, pv, f, a.battery, a.tariff, decay=0.6),
}
for season, d in peaks.items():
    idx = ds.day_index(d)
    for mid, a in agents.items():
        if a.battery is None or a.group == "home" or a.group == "housezero": continue
        la = ds.series(mid).reindex(idx).interpolate(limit=3).bfill().ffill().values
        pv = ds.series(mid, "baseline", "pv_kw").reindex(idx).fillna(0).values if a.pv_kwdc > 0 else np.zeros(len(idx))
        f = C[(mid, d, "baseline", 0.0)]
        B = lambda s: bill(s["import_kw"], s["export_kw"], a.tariff, 1.0, months=0)["total_usd"]
        pf = optimize_battery(la, pv, a.battery, a.tariff); pf = simulate_schedule(a.battery, la, pv, pf["charge_kw"], pf["discharge_kw"], 1.0)
        r = {"season": season, "mid": mid, "no_battery": B({"import_kw": np.clip(la - pv, 0, None), "export_kw": np.clip(pv - la, 0, None)}), "pf": B(pf)}
        for k, fn in V.items(): r[k] = B(fn(la, pv, f, a))
        rows.append(r)
R = pd.DataFrame(rows); R.to_csv("eval/planner_variants.csv", index=False)
for s, g in R.groupby("season"):
    gap = g.no_battery.sum() - g.pf.sum(); print(f"\n{s}: {len(g)} building batteries, best-possible saving ${gap:,.0f}")
    for k in V: print(f"  {k:20s} {(g.no_battery.sum() - g[k].sum()) / gap * 100:6.1f}%")
import json
out = {s: {"perfect_foresight": 100.0, **{k: round((g.no_battery.sum() - g[k].sum()) / (g.no_battery.sum() - g.pf.sum()) * 100, 1) for k in V},
           "n_batteries": int(len(g)), "best_saving_usd": round(float(g.no_battery.sum() - g.pf.sum()), 0)} for s, g in R.groupby("season")}
json.dump(out, open("eval/planner_summary.json", "w"), indent=1); print(out)
