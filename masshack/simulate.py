"""Run one day of the collective, hour by hour, and score it against simpler strategies.

Loop:  forecast every member -> each plans its own battery -> grid signal per hour -> members offer flex ->
       coordinator pools and assigns -> trust layer checks limits -> realize with ACTUAL 2025-26 data ->
       signed receipts -> revenue split.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import weather_forecast
from .physics import bill, simulate_schedule, peak_guard
from .optimizer import optimize_battery, vendor_default, mpc_realize, mpc_realize_robust
from .coordinator import Signal, assign, split_revenue
from .trust import TrustLayer, Command

PEAK_SIGNAL_USD_PER_KWH = 0.10          # coordinator's day-ahead price signal for flagged hours (assumption)
DR_USD_PER_KW_EVENT = 200.0 / 40.0 / 3   # $200/kW-season over ~40 three-hour events, per event-hour (assumption)


def year_thresholds(grid: pd.DataFrame) -> dict:
    return {"hi_load": float(grid["system_load_mw"].quantile(0.90)), "hi_price": float(grid["lmp_usd_mwh"].quantile(0.95)),
            "lo_price": float(grid["lmp_usd_mwh"].quantile(0.10))}


def day_signals(grid_day: pd.DataFrame, thr: dict, comm_import, comm_export, target_share=0.15, top_k: int = 4) -> list[Signal]:
    out = []
    top_hours = set(np.argsort(-grid_day["system_load_mw"].values)[:top_k])
    top_price = set(np.argsort(-grid_day["lmp_usd_mwh"].fillna(0).values)[:top_k])
    for i, (t, r) in enumerate(grid_day.iterrows()):
        reasons = []
        if bool(r.get("dr_event", False)):
            reasons.append("demand-response event (synthetic calendar)")
        if i in top_hours and r["system_load_mw"] >= thr["hi_load"]:
            reasons.append(f"ISO-NE load {r['system_load_mw']:,.0f} MW, one of the day's peak hours (top 10% of the year)")
        if i in top_price and r["lmp_usd_mwh"] >= thr["hi_price"]:
            reasons.append(f"Boston price ${r['lmp_usd_mwh']:.0f}/MWh, top 5% of the year")
        if reasons:
            value = DR_USD_PER_KW_EVENT if r.get("dr_event", False) else max(r["lmp_usd_mwh"], 0) / 1000 * 2
            out.append(Signal(i, "use_less", target_share * comm_import[i], value, reasons))
        elif r["lmp_usd_mwh"] <= thr["lo_price"] and comm_export[i] > 0.05:
            out.append(Signal(i, "soak_up", comm_export[i], max(-r["lmp_usd_mwh"], 0) / 1000 + 0.02,
                              [f"price ${r['lmp_usd_mwh']:.0f}/MWh, bottom 10%", "members exporting solar"]))
        else:
            out.append(Signal(i, "normal", 0.0, 0.0, []))
    return out


HEAT_WARNING_C = 32.2   # 90 F: Boston opens cooling centers around this level (heat advisory / warning tiers)


def simulate_day(ds, agents: dict, forecaster, date: str, trust: TrustLayer | None = None, target_share: float = 0.15,
                 force_event: bool = False, plan_only: bool = False, temp_shift_c: float = 0.0) -> dict:
    idx = ds.day_index(date)
    day_start = idx[0]
    dt = ds.dt
    wfc = weather_forecast(ds.weather, date, idx)
    trust = trust or TrustLayer()
    thr = year_thresholds(ds.grid)
    grid_day = ds.grid.reindex(idx)
    if force_event:
        grid_day = grid_day.copy()
        win = [15, 16, 17] if idx[0].month in (6, 7, 8, 9) else [7, 8]
        grid_day.loc[grid_day.index.hour.isin(win), "dr_event"] = True

    if temp_shift_c:
        wfc = wfc.copy(); wfc["outdoor_temp_c"] = wfc["outdoor_temp_c"] + temp_shift_c
    # public missions become hard limits: on a heat-warning day cooling centers keep half their battery and stay cool
    heat_warning = bool(np.nanmax(wfc["outdoor_temp_c"].values) >= HEAT_WARNING_C)
    for a in agents.values():
        if getattr(a, "cooling_center", False) and a.limits is not None:
            a.limits.min_soc = max(getattr(a, "base_min_soc", 0.2), 0.5) if heat_warning else getattr(a, "base_min_soc", 0.2)
            a.limits.allow_building_modes = not heat_warning
            if heat_warning:
                a.modes = ["baseline"]

    # 1-2. forecast and own plans (round 1: everyone plans alone)
    for a in agents.values():
        a.forecast_day(forecaster, day_start, wfc)
        a.plan_day(prior_peak_kw=0.0, dt=dt)
        a.solo_plan = a.plan
    comm_imp1 = np.sum([a.plan["import_kw"] for a in agents.values()], 0)
    comm_exp1 = np.sum([a.plan["export_kw"] for a in agents.values()], 0)
    sig1 = day_signals(grid_day, thr, comm_imp1, comm_exp1, target_share)
    # round 2: the coordinator flags the community's own peak hours and the grid-need hours with a small price
    # signal, and members with batteries re-plan. Solo plans tend to charge together and raise the community peak.
    peak_hours = set(int(h) for h in np.argsort(-comm_imp1)[:4])        # the community's own planned peak hours
    flagged = peak_hours | {x.hour_index for x in sig1 if x.kind == "use_less"}
    adder = np.zeros(len(idx)); adder[list(flagged)] = PEAK_SIGNAL_USD_PER_KWH
    for a in agents.values():
        if a.battery is not None:
            own_peak = float(np.max(a.solo_plan["import_kw"]))     # shifting must never create a new peak for the member
            caps = {h: own_peak for h in range(len(idx))}
            # ...nor push more load into the community's peak hours than the member's solo plan had there
            caps.update({h: float(a.solo_plan["import_kw"][h]) for h in range(len(idx))
                         if h in peak_hours or comm_imp1[h] >= 0.97 * comm_imp1.max()})
            a.plan_day(prior_peak_kw=0.0, dt=dt, price=a.tariff.energy_usd_per_kwh + adder, import_cap=caps)
    comm_imp = np.sum([a.plan["import_kw"] for a in agents.values()], 0)
    comm_exp = np.sum([a.plan["export_kw"] for a in agents.values()], 0)
    coordination_round = {"flagged_hours": sorted(int(h) for h in flagged), "price_signal_usd_per_kwh": PEAK_SIGNAL_USD_PER_KWH,
                          "community_plan_round1_kw": comm_imp1.round(2).tolist(), "community_plan_round2_kw": comm_imp.round(2).tolist(),
                          "planned_peak_round1_kw": round(float(comm_imp1.max()), 2), "planned_peak_round2_kw": round(float(comm_imp.max()), 2)}
    comm_fc = comm_imp.copy()   # planned community import: the baseline for the rebound check

    # 3-5. signals, offers, assignment, trust
    signals = day_signals(grid_day, thr, comm_imp, comm_exp, target_share)
    sig_hours = [(s.hour_index, s.kind) for s in signals if s.kind != "normal"]
    all_offers = {a.member_id: a.offers(sig_hours, dt) for a in agents.values()}
    hours_log, accepted_by_member = [], {}
    current_peak = float(comm_imp.max())
    for s in signals:
        if s.kind == "normal":
            continue
        pool = [o for offs in all_offers.values() for o in offs if o.hour_index == s.hour_index]
        acc, rej = assign(pool, s, comm_fc, current_peak)
        decisions = []
        for off, kw in acc:
            a = agents[off.member_id]
            soc_after = None
            if off.source == "battery" and a.plan.get("soc") is not None:
                soc_after = float(a.plan["soc"][s.hour_index]) - (kw * dt / a.battery.capacity_kwh if s.kind == "use_less" else -kw * dt / a.battery.capacity_kwh)
            cmd = Command(off.member_id, idx[s.hour_index].isoformat(), s.kind, kw, off.source, s.value_usd_per_kw * kw)
            d = trust.execute_or_block(cmd, a.limits, idx[s.hour_index].hour, soc_after)
            decisions.append({"member": off.member_id, "kw": round(kw, 3), "source": off.source,
                              "usd_per_kw": round(off.usd_per_kw, 3), "accepted": d.accepted, "reason": d.reason})
            if d.accepted:
                accepted_by_member.setdefault(off.member_id, []).append((s, off, kw))
                comm_fc[s.hour_index] += -kw if s.kind == "use_less" else kw
                if off.rebound_kw is not None:
                    comm_fc += off.rebound_kw * kw / off.kw
        # demonstrate the trust layer: one deliberately oversized request per signal hour is refused
        if acc:
            off0, kw0 = acc[0]
            big = Command(off0.member_id, idx[s.hour_index].isoformat(), s.kind, agents[off0.member_id].limits.max_down_kw * 2 + 1, off0.source, 0)
            d = trust.execute_or_block(big, agents[off0.member_id].limits, idx[s.hour_index].hour, None)
            decisions.append({"member": off0.member_id, "kw": round(big.kw, 3), "source": off0.source, "usd_per_kw": None,
                              "accepted": d.accepted, "reason": d.reason, "demo_overreach": True})
        hours_log.append({"hour": idx[s.hour_index].isoformat(), "kind": s.kind, "target_kw": round(s.target_kw, 2),
                          "value_usd_per_kw": round(s.value_usd_per_kw, 3), "reasons": s.reasons,
                          "offers": [{"member": o.member_id, "kw": round(o.kw, 3), "usd_per_kw": round(o.usd_per_kw, 3), "source": o.source} for o in pool],
                          "decisions": decisions,
                          "rejected_by_coordinator": [{"member": o.member_id, "source": o.source, "reason": why} for o, why in rej]})

    if plan_only:
        return {"date": date, "temp_shift_c": temp_shift_c, "heat_warning": heat_warning, "hours": [t.isoformat() for t in idx],
                "temp_forecast_c": wfc["outdoor_temp_c"].round(2).tolist(),
                "planned_round1_kw": comm_imp1.round(1).tolist(), "planned_round2_kw": comm_imp.round(1).tolist(),
                "after_assignment_kw": np.asarray(comm_fc).round(1).tolist(),
                "signals": [x.kind for x in signals],
                "assigned": {mid: [{"hour": idx[s_.hour_index].isoformat()[11:16], "kw": round(kw, 2), "source": off.source} for s_, off, kw in v]
                             for mid, v in accepted_by_member.items()},
                "accepted_kw_by_source": pd.DataFrame([(off.source, kw) for v in accepted_by_member.values() for _, off, kw in v],
                                                      columns=["source", "kw"]).groupby("source").kw.sum().round(1).to_dict() if accepted_by_member else {},
                "modes_chosen": {mid: off.source for mid, v in accepted_by_member.items() for _, off, _ in v if off.source != "battery"}}

    # 6. realize with actual data, receipts, settlement
    members_out, delivered, member_cost, receipts = {}, {}, {}, []
    for mid, a in agents.items():
        load_act = ds.series(mid, "baseline").reindex(idx).interpolate(limit=3).bfill().ffill().values
        pv_act = ds.series(mid, "baseline", "pv_kw").reindex(idx).fillna(0).values if a.pv_kwdc > 0 else np.zeros(len(idx))
        strategies = {}
        strategies["no_battery"] = {"import_kw": np.clip(load_act - pv_act, 0, None), "export_kw": np.clip(pv_act - load_act, 0, None)}
        acc = accepted_by_member.get(mid, [])
        mode_used = next((off.source for s, off, kw in acc if off.source not in ("battery",)), "baseline")
        load_coll = ds.series(mid, mode_used).reindex(idx).interpolate(limit=3).bfill().ffill().values if mode_used != "baseline" else load_act
        if a.battery is not None:
            strategies["vendor_default"] = vendor_default(load_act, pv_act, a.battery, dt)
            # each battery re-plans every hour as the actual load is revealed (model predictive control)
            fc_load = np.maximum(a.fc["p50"].values, a.fc["p90"].values * 0.9)
            fq = {k: a.fc[k].values for k in ("p10", "p50", "p90")}
            # hourly re-planning against forecast SCENARIOS (stochastic MPC): see eval/planner_variants.py
            strategies["own_optimizer"] = mpc_realize_robust(load_act, pv_act, fq, a.battery, a.tariff, dt)
            forced = {s.hour_index: (-kw if s.kind == "use_less" else kw) for s, off, kw in acc if off.source == "battery"}
            if forced:
                net = a.plan["import_kw"] - a.plan["export_kw"]
                coll_plan = optimize_battery(a.plan["planning_load"], a.pv_fc, a.battery, a.tariff, dt=dt, prior_peak_kw=0.0,
                                             price_usd_per_kwh=a.plan.get("price"), forced_import_delta=forced, base_import=net)
                if not coll_plan.get("ok"):
                    coll_plan = a.plan
            else:
                coll_plan = a.plan
            solo_peak = float(np.max(a.solo_plan["import_kw"]))
            # outside committed hours a battery may not import more than its own plan: no pre-charging at the community peak
            caps = {hh: float(a.plan["import_kw"][hh]) + 0.02 * solo_peak for hh in range(len(idx))}
            caps.update({hh: float(coll_plan["import_kw"][hh]) for hh in forced if forced[hh] < 0})
            dlt = (load_coll - load_act) if mode_used != "baseline" else 0.0
            fq_coll = {k: v + dlt for k, v in fq.items()}
            strategies["collective"] = mpc_realize_robust(load_coll, pv_act, fq_coll, a.battery, a.tariff, dt, import_cap=caps,
                                                          price=a.plan.get("price"))
            pf = optimize_battery(load_act, pv_act, a.battery, a.tariff, dt=dt)
            strategies["perfect_foresight"] = simulate_schedule(a.battery, load_act, pv_act, pf["charge_kw"], pf["discharge_kw"], dt)
        else:
            strategies["own_optimizer"] = strategies["no_battery"]
            strategies["collective"] = {"import_kw": np.clip(load_coll - pv_act, 0, None), "export_kw": np.clip(pv_act - load_coll, 0, None)}
        bills = {k: bill(v["import_kw"], v["export_kw"], a.tariff, dt, months=0) for k, v in strategies.items()}
        # deliveries vs the member's own plan
        for s, off, kw in acc:
            h = s.hour_index
            got = (strategies["own_optimizer"]["import_kw"][h] - strategies["own_optimizer"]["export_kw"][h]) - \
                  (strategies["collective"]["import_kw"][h] - strategies["collective"]["export_kw"][h])
            got = got if s.kind == "use_less" else -got
            got = max(got, 0.0)
            delivered[mid] = delivered.get(mid, 0.0) + got
            member_cost[mid] = member_cost.get(mid, 0.0) + off.cost_usd * kw / off.kw
            cmd = Command(mid, idx[h].isoformat(), s.kind, kw, off.source, s.value_usd_per_kw * kw)
            receipts.append(trust.sign_receipt(cmd, got, s.value_usd_per_kw * got))
        members_out[mid] = {
            "role": a.role, "building_type": a.building_type, "zip": a.zip, "sqft": a.sqft, "source": a.source,
            "battery_kwh": a.battery.capacity_kwh if a.battery else 0, "battery_kw": a.battery.power_kw if a.battery else 0,
            "pv_kwdc": a.pv_kwdc, "mode_used": mode_used,
            "load_actual_kw": load_act.round(3).tolist(), "pv_actual_kw": pv_act.round(3).tolist(),
            "forecast_p10": a.fc["p10"].round(3).tolist(), "forecast_p50": a.fc["p50"].round(3).tolist(), "forecast_p90": a.fc["p90"].round(3).tolist(),
            "strategies": {k: {"import_kw": np.asarray(v["import_kw"]).round(3).tolist(), "export_kw": np.asarray(v["export_kw"]).round(3).tolist(),
                               "soc": (np.asarray(v["soc"]).round(3).tolist() if v.get("soc") is not None else None)} for k, v in strategies.items()},
            "bills": {k: {kk: round(vv, 2) for kk, vv in b.items()} for k, b in bills.items()},
        }

    grid_value = sum(s.value_usd_per_kw * sum(max((members_out[m]["strategies"]["own_optimizer"]["import_kw"][s.hour_index] -
                                                    members_out[m]["strategies"]["collective"]["import_kw"][s.hour_index]), 0)
                                                for m in members_out) for s in signals if s.kind == "use_less")
    payouts = split_revenue(delivered, grid_value, member_cost)

    keys = ["no_battery", "vendor_default", "own_optimizer", "collective", "perfect_foresight"]

    def pick(m, k, what):  # members without a battery have no vendor/perfect strategies: same as no battery
        return m[what].get(k, m[what]["no_battery"])

    community = {k: np.sum([pick(m, k, "strategies")["import_kw"] for m in members_out.values()], 0).round(2).tolist() for k in keys}
    need = [s.hour_index for s in signals if s.kind == "use_less"]
    summary = {k: {"peak_kw": round(float(np.max(community[k])), 2),
                   "need_hours_kw": round(float(np.mean([community[k][i] for i in need])), 2) if need else None,
                   "bill_usd": round(sum(pick(m, k, "bills")["total_usd"] for m in members_out.values()), 2)} for k in keys}
    return {
        "date": date, "hours": [t.isoformat() for t in idx],
        "weather": {"temp_c": ds.weather["outdoor_temp_c"].reindex(idx).round(2).tolist(),
                    "temp_forecast_c": wfc["outdoor_temp_c"].round(2).tolist(),
                    "ghi_w_m2": ds.weather["ghi_w_m2"].reindex(idx).round(1).tolist()},
        "grid": {"lmp_usd_mwh": grid_day["lmp_usd_mwh"].round(2).tolist(), "system_load_mw": grid_day["system_load_mw"].round(0).tolist(),
                 "signal": [s.kind for s in signals], "reasons": [s.reasons for s in signals]},
        "community": community, "summary": summary, "coordinator_log": hours_log, "coordination_round": coordination_round,
        "heat_warning": heat_warning,
        "receipts": receipts, "trust_public_key": trust.public_key_hex(),
        "refused_commands": [e for e in trust.log if e.get("type") == "command" and not e["accepted"]],
        "payouts_usd": {k: round(v, 2) for k, v in payouts.items()}, "grid_value_usd": round(grid_value, 2),
        "delivered_kwh": {k: round(v * dt, 3) for k, v in delivered.items()},
        "members": members_out,
    }
