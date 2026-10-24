"""End-to-end pipeline: data -> forecasters -> evaluation -> two peak days -> Boston -> demo JSON.

    python run_all.py                       # data/model_inputs -> app/public/demo.json (~20 min on 2 CPU cores)
    python run_all.py --reuse               # reuse app/forecast_cache.pkl, skip training (~1 min)
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from masshack.data import Dataset, weather_forecast, eval_split, season_of
from masshack.physics import Tariff
from masshack.agents import build_agents
from masshack.world_model import WorldModelForecaster
from masshack.forecast import LGBMForecaster, seasonal_naive, HybridForecaster
from masshack.forecast_v2 import Calibrated, DeltaModel, EffectForecaster, FeatureBuilder
from masshack.simulate import simulate_day
from masshack.trust import TrustLayer
from masshack.boston import per_sqft_effects, project


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/model_inputs")
    ap.add_argument("--out", default="app/public/demo.json")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--reuse", action="store_true", help="reuse cached forecasts and metrics (skip training)")
    args = ap.parse_args()
    t0 = time.time()
    log = lambda *a: print(f"[{time.time() - t0:6.1f}s]", *a, flush=True)

    ds = Dataset(args.data)
    tariff = Tariff.from_json(Path(args.data) / "tariff.json") if (Path(args.data) / "tariff.json").exists() else Tariff()
    agents = build_agents(ds, tariff)
    peaks = ds.pick_peak_days()
    log("members", len(agents), "| prosumers", sum(a.role == "prosumer" for a in agents.values()), "| peak days", peaks)

    # ----- whole-week split: train / calibration / test (~104 test days across every season, incl. both peak weeks) ---
    all_days, train_days, cal_days, test_days = eval_split(ds)
    log(f"split: train {len(train_days)} days · calibration {len(cal_days)} · test {len(test_days)}")

    cache_path = Path(args.out).parent.parent / "forecast_cache.pkl"
    if args.reuse and cache_path.exists():
        import pickle
        C = pickle.load(open(cache_path, "rb"))
        fc_metrics, forecaster_name, latent_map, lat_member = C["metrics"], C["used"], C["latent"], C["lat_member"]
        forecaster = CachedForecaster(C["fc"]); forecaster.extra = C.get("extra", {})
        log("reusing cached forecasts", cache_path)
    else:
        fc_metrics, forecaster_name, latent_map, lat_member, forecaster = train_and_eval(ds, agents, peaks, all_days, train_days, test_days, args, log, cache_path, cal_days)
    run_days(ds, agents, peaks, forecaster, forecaster_name, fc_metrics, latent_map, lat_member, tariff, args, log)


class CachedForecaster:
    def __init__(self, fc, shift=0.0):
        self.fc, self.shift = fc, shift

    def forecast(self, member, day_start, mode="baseline", weather_fc=None):
        return self.fc[(member, str(day_start.date()), mode, self.shift)]


def member_type(r):
    g = str(r.get("group", ""))
    return {"housezero": "housezero", "civic_measured": "library_central"}.get(g, str(r.get("building_type", "other")))


def train_and_eval(ds, agents, peaks, all_days, train_days, test_days, args, log, cache_path, cal_days=()):
    all_members = list(ds.members.index)                       # community + training-only homes
    types = {m: member_type(r) for m, r in ds.members.iterrows()}
    groups = {m: a.group for m, a in agents.items()}
    modes = sorted({m for mid in all_members for m in ds.modes(mid)})
    wm = WorldModelForecaster(ds, all_members, modes, member_types=types).fit(train_days, epochs=args.epochs, log=log)
    lgbm = LGBMForecaster(ds); lgbm_nw = LGBMForecaster(ds, use_weather=False)
    rng = np.random.default_rng(0)
    ablate = set(rng.choice(list(agents), size=min(30, len(agents)), replace=False)) | {"hz_main", "bpl_central"}
    for mid in agents:
        lgbm.fit(mid, train_days, "baseline")
        if mid in ablate:
            lgbm_nw.fit(mid, train_days, "baseline")
    log("forecasters trained")
    wfc_of = lambda d: weather_forecast(ds.weather, str(d.date()), ds.day_index(str(d.date())))
    lgbm_cal = Calibrated(lgbm, groups); k_l = lgbm_cal.calibrate(ds, list(agents), cal_days, weather_fn=wfc_of)
    wm_cal = Calibrated(wm, groups); k_w = wm_cal.calibrate(ds, list(agents), cal_days, weather_fn=wfc_of)
    log("band calibration (x half-width) lightgbm", {g: round(v, 2) for g, v in k_l.items()}, "world model", {g: round(v, 2) for g, v in k_w.items()})

    # ----- action effects: paired-difference LightGBM per mode -------------------------------------------------
    fb = FeatureBuilder(ds)
    tr_idx = np.concatenate([np.arange(fb.pos[d], fb.pos[d] + 24) for d in train_days if d in fb.pos])
    scale = {}
    for m in all_members:
        y = ds.series(m).reindex(fb.tindex).values
        scale[m] = float(np.nanmean(y[tr_idx[tr_idx < len(y)]])) or 1.0
    mode_members = {}
    for m in all_members:
        for x in ds.modes(m):
            if x != "baseline":
                mode_members.setdefault(x, []).append(m)
    delta = DeltaModel(ds, fb, scale, types).fit(mode_members, train_days, log=log)

    # ----- evaluation on held-out days (day-ahead weather forecast, no leakage) -------------------------------
    rows, agg = [], {}
    for d in test_days:
        wfc = wfc_of(d)
        for mid, a in agents.items():
            y = ds.series(mid).reindex(ds.day_index(str(d.date()))).values
            if np.isnan(y).any() or np.nanmean(y) <= 0:
                continue
            preds = {"world_model": wm_cal.forecast(mid, d, "baseline", wfc), "lightgbm": lgbm_cal.forecast(mid, d, "baseline", wfc),
                     "lightgbm_uncalibrated": lgbm.forecast(mid, d, "baseline", wfc), "seasonal_naive": seasonal_naive(ds.series(mid), d)}
            if mid in ablate:
                preds["lightgbm_no_weather"] = lgbm_nw.forecast(mid, d)
            for k, p in preds.items():
                if p.isna().any().any():
                    continue
                p10, p50, p90 = p["p10"].values, p["p50"].values, p["p90"].values
                rows.append({"model": k, "member": mid, "group": a.group, "season": season_of(d),
                             "mae_pct": float(np.mean(np.abs(p50 - y)) / max(np.mean(y), 1e-6) * 100),
                             "peak_err_pct": float(abs(p50.max() - y.max()) / max(y.max(), 1e-6) * 100),
                             "coverage": float(np.mean((y >= p10) & (y <= p90)))})
                if k in ("lightgbm", "world_model"):
                    g_ = agg.setdefault((k, d), [0, 0]); g_[0] = g_[0] + y; g_[1] = g_[1] + p50
    ev = pd.DataFrame(rows)
    fc_metrics = ev.groupby(["model", "season"])[["mae_pct", "peak_err_pct", "coverage"]].mean().round(2).reset_index().to_dict("records")
    by_group = ev.groupby(["group", "model"])["mae_pct"].mean().round(2).unstack().reset_index().to_dict("records")
    by_group_peak = ev.groupby(["group", "model"])["peak_err_pct"].mean().round(2).unstack().reset_index().to_dict("records")
    by_group_cov = ev.groupby(["group", "model"])["coverage"].mean().round(2).unstack().reset_index().to_dict("records")
    real = ev[ev.member.isin(["hz_main", "bpl_central"])].groupby(["member", "model", "season"])["mae_pct"].mean().round(2).reset_index().to_dict("records")
    community = pd.DataFrame([{"model": k, "mae_pct": float(np.mean(np.abs(v[1] - v[0])) / np.mean(v[0]) * 100),
                               "peak_err_pct": float(abs(v[1].max() - v[0].max()) / v[0].max() * 100)} for (k, _), v in agg.items()]
                             ).groupby("model").mean().round(2).reset_index().to_dict("records")
    hm = [m for m, a in agents.items() if a.group == "home"]
    agg_rows = []
    for d in test_days:
        wfc = wfc_of(d)
        ys = [ds.series(m).reindex(ds.day_index(str(d.date()))).values for m in hm]
        if any(np.isnan(y).any() for y in ys):
            continue
        y = np.sum(ys, 0)
        for k, f in (("world_model", wm), ("lightgbm", lgbm)):
            pf = np.sum([f.forecast(m, d, "baseline", wfc)["p50"].values for m in hm], 0)
            agg_rows.append({"model": k, "mae_pct": float(np.mean(np.abs(pf - y)) / np.mean(y) * 100)})
    homes_agg = pd.DataFrame(agg_rows).groupby("model").mae_pct.mean().round(2).to_dict() if agg_rows else {}

    # ----- action-effect evaluation: predicted vs actual change from baseline, held-out days ----------------
    er = []
    for d in test_days:
        wfc = wfc_of(d); idx = ds.day_index(str(d.date()))
        for mode, ms in mode_members.items():
            for m in ms:
                if m not in agents:
                    continue
                yb = ds.series(m).reindex(idx).values; ym = ds.series(m, mode).reindex(idx).values
                if np.isnan(yb).any() or np.isnan(ym).any() or np.abs(ym - yb).max() < 1e-6:
                    continue
                act = ym - yb; pk = int(np.argmax(yb)); sc = float(yb.max())
                b = lgbm_cal.forecast(m, d, "baseline", wfc)
                cands = {"delta_lgbm": delta.effect(m, d, mode, b.p50.values, wfc) if mode in delta.models else np.zeros(24),
                         "world_model": (wm.forecast(m, d, mode, wfc)["p50"] - wm.forecast(m, d, "baseline", wfc)["p50"]).values,
                         "none": np.zeros(24)}
                for k, pe in cands.items():
                    er.append({"model": k, "mode": mode, "mae_pct_of_peak": float(np.mean(np.abs(pe - act)) / sc * 100),
                               "corr": float(np.corrcoef(pe, act)[0, 1]) if pe.std() > 0 and act.std() > 0 else np.nan,
                               "sign_ok": float(np.sign(round(pe[pk], 6)) == np.sign(round(act[pk], 6))),
                               "pred_kw_at_peak": float(pe[pk]), "act_kw_at_peak": float(act[pk])})
    E = pd.DataFrame(er)
    eff = E.groupby(["mode", "model"]).agg(n=("corr", "size"), mae_pct_of_peak=("mae_pct_of_peak", "mean"), corr=("corr", "median"),
                                          sign_ok=("sign_ok", "mean"), pred_kw_at_peak=("pred_kw_at_peak", "sum"),
                                          act_kw_at_peak=("act_kw_at_peak", "sum")).round(3).reset_index()
    choice = {}
    for mode, g in eff.groupby("mode"):
        g2 = g[g.model != "none"].sort_values("mae_pct_of_peak")
        best = g2.iloc[0]
        none = float(g[g.model == "none"].mae_pct_of_peak.iloc[0])
        choice[mode] = best.model if best.mae_pct_of_peak < none else "none"
    log("action effects", eff.to_dict("records")); log("effect model chosen per mode", choice)
    log("forecast metrics", fc_metrics); log("community total", community); log("by group", by_group); log("40 homes combined", homes_agg)
    best = ev.groupby("model")["mae_pct"].mean()
    # ----- final models: everything above was scored on held-out weeks; the planner's models are now refit on every
    # day EXCEPT the weeks around the two simulated peak days (those stay unseen), keeping the calibrated band widths.
    peak_weeks = set()
    for d in peaks.values():
        c = pd.Timestamp(d, tz=ds.weather.index.tz); peak_weeks |= {c + pd.Timedelta(days=k) for k in range(-3, 4)}
    final_days = [d for d in all_days if d not in peak_weeks]
    lgbm_f = LGBMForecaster(ds)
    for mid in agents:
        lgbm_f.fit(mid, final_days, "baseline")
    lgbm_fc = Calibrated(lgbm_f, groups); lgbm_fc.k = dict(k_l)
    delta_f = DeltaModel(ds, fb, scale, types).fit(mode_members, final_days)
    log(f"final planner models refit on {len(final_days)} days (peak weeks held out)")
    base, base_name = (wm_cal, "world model (calibrated)") if best["world_model"] <= best["lightgbm"] else (lgbm_fc, "lightgbm (calibrated)")
    forecaster = EffectForecaster(base, wm, delta_f, choice, base_name)
    forecaster_name = f"{base_name} baseline + action effects ({', '.join(f'{k}: {v}' for k, v in sorted(choice.items()))})"
    log("planner uses", forecaster_name, best.round(2).to_dict())
    from sklearn.decomposition import PCA
    lat_member = "hz_main" if "hz_main" in agents else list(agents)[0]
    lat = wm.daily_latents(lat_member, all_days)
    xy = PCA(2, random_state=0).fit_transform(lat.values)
    tmax = ds.weather["outdoor_temp_c"].resample("1D").max()
    latent_map = [{"date": str(d.date()), "x": round(float(a), 3), "y": round(float(b), 3),
                   "tmax_c": round(float(tmax.get(d, np.nan)), 1), "weekend": bool(d.weekday() >= 5)} for d, (a, b) in zip(lat.index, xy)]
    fc = {}
    for season, d in peaks.items():
        ds0 = pd.Timestamp(d, tz=ds.weather.index.tz)
        shifts = (-10.0, -5.0, 0.0, 3.0) if season == "summer" else (0.0,)
        for sh in shifts:
            wfc = weather_forecast(ds.weather, d, ds.day_index(d))
            wfc["outdoor_temp_c"] = wfc["outdoor_temp_c"] + sh
            for mid, a in agents.items():
                for m in ds.modes(mid):
                    fc[(mid, d, m, sh)] = forecaster.forecast(mid, ds0, m, wfc)
    extra = {"by_group": by_group, "by_group_peak": by_group_peak, "by_group_coverage": by_group_cov, "real_buildings": real,
             "homes_combined": homes_agg, "community_total": community, "effects": eff.to_dict("records"), "effect_choice": choice,
             "calibration": {"lightgbm": k_l, "world_model": k_w},
             "split": {"train_days": len(train_days), "calibration_days": len(cal_days), "test_days": len(test_days)},
             "type_count": len(wm.types), "train_members": len(all_members)}
    import pickle
    pickle.dump({"metrics": fc_metrics, "used": forecaster_name, "latent": latent_map, "lat_member": lat_member, "fc": fc, "extra": extra},
                open(cache_path, "wb"))
    cf = CachedForecaster(fc); cf.extra = extra
    return fc_metrics, forecaster_name, latent_map, lat_member, cf


def run_days(ds, agents, peaks, forecaster, forecaster_name, fc_metrics, latent_map, lat_member, tariff, args, log):
    # ----- simulate both peak days -----------------------------------------------------------------
    trust = TrustLayer(seed=b"masshack-demo-coordinator-key-01"[:32])
    days = {}
    for season, d in peaks.items():
        days[season] = simulate_day(ds, agents, forecaster, d, trust=trust)
        log(season, d, json.dumps(days[season]["summary"]))

    # ----- temperature what-if: same summer day, weather forecast shifted; plans and actions only ------------
    whatif = {}
    for sh in (-10.0, -5.0, 0.0, 3.0):
        f = CachedForecaster(forecaster.fc, sh)
        if not any(k[3] == sh for k in forecaster.fc):
            continue
        whatif[str(sh)] = simulate_day(ds, agents, f, peaks["summer"], trust=TrustLayer(seed=b"w" * 32), plan_only=True, temp_shift_c=sh)
        w = whatif[str(sh)]
        log("what-if", sh, "heat warning", w["heat_warning"], "planned peak r1/r2", max(w["planned_round1_kw"]), max(w["planned_round2_kw"]),
            "accepted kW", w["accepted_kw_by_source"])

    # ----- Boston projection ------------------------------------------------------------------------
    stock = ds.stock
    civic_stock = Path(args.data) / "boston_stock_civic.csv"
    if civic_stock.exists():
        stock = pd.concat([stock, pd.read_csv(civic_stock, dtype={"zip": str})], ignore_index=True)
    boston = {season: project(stock, per_sqft_effects(day)) for season, day in days.items()}
    log("boston", {s: b["citywide"] for s, b in boston.items()})

    out = {
        "generated": pd.Timestamp.now(tz="America/New_York").isoformat(),
        "period": "2025-05-01 to 2026-06-01 (America/New_York)",
        "tariff": tariff.__dict__, "peak_days": peaks, "forecaster_used": forecaster_name,
        "forecast_metrics": fc_metrics, "forecast_extra": getattr(forecaster, "extra", {}), "whatif": whatif, "days": days, "boston": boston, "latent_map": {"member": lat_member, "points": latent_map},
        "members_table": [{"member_id": k, "role": a.role, "building_type": a.building_type, "sqft": a.sqft, "zip": a.zip,
                           "source": a.source, "battery_kwh": round(a.battery.capacity_kwh, 1) if a.battery else 0,
                           "pv_kwdc": round(a.pv_kwdc, 1), "modes": a.modes, "group": a.group,
                           "cooling_center": getattr(a, "cooling_center", False), "min_soc": a.limits.min_soc if a.limits else None} for k, a in agents.items()],
        "planner_eval": json.loads(Path("eval/planner_summary.json").read_text()) if Path("eval/planner_summary.json").exists() else None,
        "sources": {
            "housezero": "Harvard CGBC HouseZero 2025-26 dataset (Jun 2025-May 2026, DOI 10.6084/m9.figshare.32790984.v1) plus May 2025 from the earlier release, CC BY 4.0",
            "weather": "HouseZero weather station (measured), 2025-26",
            "business_members": "NREL ComStock 2025 Release 3 Boston building designs used as physics templates, driven by HouseZero 2025-26 weather",
            "library": "Boston Public Library Central Library 5-min meter, May 2025-May 2026, City of Boston / Analyze Boston, PDDL",
            "homes": "Synthetic single-family homes from the team's homesim generator (seed 42), HouseZero weather and PV, evening peak calibrated toward National Grid R-1",
            "grid": "ISO-NE real-time hourly LMP .Z.NEMASSBOST and system load, 2025-26 (via gridstatus)",
            "stock": "City of Boston BERDO 2026 disclosure (2025 data), buildings >= 20,000 sq ft",
            "tariff": tariff.source, "dr_events": "synthetic ConnectedSolutions-style calendar",
        },
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    def clean(o):   # browsers reject NaN/Infinity in JSON
        if isinstance(o, float):
            return o if np.isfinite(o) else None
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if hasattr(o, "tolist"):
            return clean(o.tolist())
        return o
    Path(args.out).write_text(json.dumps(clean(out), default=str, allow_nan=False))
    log("wrote", args.out, f"{Path(args.out).stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
