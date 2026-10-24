"""Experiment 1: how much of the battery savings gap is forecast error vs. the planner itself?
Prosumers on both peak days; cached forecasts (trained with the peak weeks held out)."""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "eval"))
DATA = os.environ.get("MASSHACK_DATA", str(ROOT / "data" / "model_inputs"))
import sys, pickle, numpy as np, pandas as pd
from pathlib import Path
from masshack.data import Dataset
from masshack.physics import Tariff, bill, simulate_schedule
from masshack.agents import build_agents
from masshack.optimizer import optimize_battery, mpc_realize
ds = Dataset(DATA); tariff = Tariff.from_json(Path(DATA) / "tariff.json"); agents = build_agents(ds, tariff)
C = pickle.load(open(sys.argv[1] if len(sys.argv) > 1 else "app/forecast_cache.pkl", "rb"))["fc"]
peaks = ds.pick_peak_days(); rows = []
for season, d in peaks.items():
    idx = ds.day_index(d)
    for mid, a in agents.items():
        if a.battery is None: continue
        la = ds.series(mid).reindex(idx).interpolate(limit=3).bfill().ffill().values
        pv = ds.series(mid, "baseline", "pv_kw").reindex(idx).fillna(0).values if a.pv_kwdc > 0 else np.zeros(len(idx))
        f = C[(mid, d, "baseline", 0.0)]
        B = lambda s: bill(s["import_kw"], s["export_kw"], a.tariff, 1.0, months=0)["total_usd"]
        nb = B({"import_kw": np.clip(la - pv, 0, None), "export_kw": np.clip(pv - la, 0, None)})
        pf = optimize_battery(la, pv, a.battery, a.tariff); pf = simulate_schedule(a.battery, la, pv, pf["charge_kw"], pf["discharge_kw"], 1.0)
        r = {"season": season, "mid": mid, "group": a.group, "no_battery": nb, "perfect_foresight": B(pf)}
        r["mpc_oracle_fc"] = B(mpc_realize(la, pv, la, a.battery, a.tariff))
        for name, fc in [("mpc_p50", f.p50.values), ("mpc_current", np.maximum(f.p50.values, 0.9 * f.p90.values)), ("mpc_p90", f.p90.values)]:
            r[name] = B(mpc_realize(la, pv, fc, a.battery, a.tariff))
        op = optimize_battery(f.p50.values, pv, a.battery, a.tariff)
        r["open_loop_p50"] = B(simulate_schedule(a.battery, la, pv, op["charge_kw"], op["discharge_kw"], 1.0))
        rows.append(r)
R = pd.DataFrame(rows)
cols = ["perfect_foresight", "mpc_oracle_fc", "mpc_p50", "mpc_current", "mpc_p90", "open_loop_p50"]
for s, g in R.groupby("season"):
    gap = g.no_battery.sum() - g.perfect_foresight.sum()
    print(f"\n{s}: {len(g)} prosumers · perfect-foresight saving ${gap:,.0f}")
    for c in cols: print(f"  {c:18s} captures {(g.no_battery.sum() - g[c].sum()) / gap * 100:6.1f}%")
R.to_csv("eval/planner_gap.csv", index=False)
