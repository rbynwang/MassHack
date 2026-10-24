"""Run one Cambridge commons through June 24, 2025 (the ISO-NE peak day) and export the demo.

    uv run commonwatt-demo                       # terminal log + app/data/demo.js
    COMMONWATT_TOOL=pkg.mod:Cls uv run commonwatt-demo   # with the trained model plugged in

Scenarios: no optimization; each member optimizing alone against the same time-of-use peak; the Commonwatt network.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from commonwatt import __version__
from commonwatt.agents.coordinator import Coordinator, Negotiation, hours_label
from commonwatt.agents.grid import GridAgent
from commonwatt.agents.member import MemberAgent
from commonwatt.members import EVENT_DAY, ROOT, TOU_PEAK, build_neighborhood
from commonwatt.network import Bus, Registry
from commonwatt.protocol import Response, export_schemas
from commonwatt.tools import load_tool
from commonwatt.trust import Ledger, OwnerLimits

COMMONS = "cambridge-commons-01"
LATE_JOINER = "library_01"
OVERRIDE = ("home_03", 0.0, "guests coming over, keep it cool")   # owner tightens the limit after offering
KIND_LABEL = {"large_building": "Large buildings", "household": "Households",
              "small_business": "Small businesses", "public_institution": "Public institutions"}


def owner_limits(tw) -> OwnerLimits:
    comfort = None
    if tw.home is not None:
        sp = tw.home.setpoint_c[np.isfinite(tw.home.setpoint_c)]
        comfort = float(sp.max() + tw.home.band_c) if sp.size else None
    return OwnerLimits(max_reduce_kw=20.0 if tw.kind == "household" else 200.0,
                       battery_reserve_pct=tw.battery["reserve_pct"] if tw.battery else None,
                       comfort_max_c=comfort)


def run(ask_kw: float, window: list[int], tool_spec: str | None = None) -> dict:
    tool = load_tool(tool_spec)
    twins, weather = build_neighborhood()
    registry, ledger = Registry(), Ledger()
    bus = Bus(registry)
    grid = GridAgent(COMMONS)
    coord = Coordinator(COMMONS, bus, registry, tool)
    agents = {t.member_id: MemberAgent(t, tool, COMMONS, owner_limits(t), ledger, weather) for t in twins}

    # 1. The network forms ------------------------------------------------------------------
    bus.at("09:55")
    for card in (grid.card(), coord.card()):
        registry.register(card)
    for m, ag in agents.items():
        if m == LATE_JOINER:
            continue
        registry.register(ag.card())
        registry.register(ag.guard_card())
        bus.send(m, ag.keys, "registry", ag.card(), f"{m} joined the commons (agent card registered)")

    # 2. Alone and no optimization ----------------------------------------------------------
    no_opt = sum(t.planned_kw for t in twins)
    alone = sum(t.alone() for t in twins)

    # 3. The grid asks; offers; negotiation ---------------------------------------------------
    bus.at("10:00")
    ask = grid.make_ask(ask_kw, window)
    bus.send(grid.id, grid.keys, coord.id, ask,
             f"Ask: reduce {ask.kw:.0f} kW, {hours_label(window)} at ${ask.price_usd_per_kwh:.2f}/kWh ({ask.reason})")
    neg = Negotiation(ask=ask)

    def collect_offer(m: str) -> None:
        ag = agents[m]
        bus.send(coord.id, coord.keys, m, ask, f"Call for offers: {hours_label(window)}")
        o = ag.make_offer(ask)
        neg.offers[m] = o
        hw = [o.hours[h] for h in window]
        bus.send(m, ag.keys, coord.id, o,
                 f"Offer: up to {min(x.can_reduce_kw for x in hw):.1f} kW less, at ${o.cost_per_kwh:.2f}/kWh")

    bus.at("10:01")
    for c in registry.members(COMMONS):
        collect_offer(c.agent_id)

    bus.at("10:02")
    m_o, kw_o, why = OVERRIDE
    agents[m_o].guard.limits.max_reduce_kw = kw_o
    bus.note(f"guard:{m_o}", f"{m_o}'s owner lowered its limit to {kw_o} kW ({why}); private, the coordinator "
                             f"still has the earlier offer", kind="private")

    bus.at("10:03")
    coord.run_round(neg, 1, agents)

    bus.at("10:04")
    lib = agents[LATE_JOINER]
    registry.register(lib.card())
    registry.register(lib.guard_card())
    bus.send(LATE_JOINER, lib.keys, "registry", lib.card(),
             f"{LATE_JOINER} joined the commons (agent card registered, no coordinator change)")
    collect_offer(LATE_JOINER)

    for r in (2, 3):
        if neg.pooled_kw >= ask.kw - 0.05:
            break
        bus.at(f"10:0{3 + r}")
        coord.run_round(neg, r, agents)

    bus.at("10:07")
    coord.stagger(neg)
    pooled = Response(request_id=ask.ask_id, member_id=COMMONS,
                      decision="accept" if neg.pooled_kw >= ask.kw - 0.05 else "counter",
                      kw=neg.pooled_kw, reason=f"{len(neg.committed)} members committed")
    bus.send(coord.id, coord.keys, grid.id, pooled, f"Pooled: {neg.pooled_kw:.1f} kW committed")
    for m, a in neg.assignments.items():
        ag = agents[m]
        bus.send(coord.id, coord.keys, m, a, f"Assignment {m}: minus {a.reduce_kw:.1f} kW"
                 + (f", recharge in {len(a.recovery_kw)} staggered hours" if a.recovery_kw else ""))
        ag.on_assignment(bus.envelope(coord.id, coord.keys, m, a))

    # 4. The day runs; guards measure and sign receipts ---------------------------------------
    bus.at("19:05")
    actual = {m: ag.actual_kw() for m, ag in agents.items()}
    network = sum(actual.values())
    receipts = {}
    for m in neg.committed:
        ag = agents[m]
        bmin = ag.battery_min_pct()
        r = ag.guard.settle(ask.ask_id, window, neg.committed[m], ag.twin.planned_kw.tolist(),
                            actual[m].tolist(), ask.price_usd_per_kwh, ag.indoor_f(),
                            round(bmin, 1) if bmin is not None else None)
        receipts[m] = r
        bus.send(f"guard:{m}", ag.guard.keys, m, r,
                 f"Receipt signed: {m}, {r.delivered_kwh:.1f} kWh, ${r.payment_usd:.2f}")
    ok, msg = ledger.verify()
    bus.note("ledger", f"Ledger check: {msg}" if ok else f"Ledger FAILED: {msg}", kind="ledger")

    return _export(twins, agents, weather, grid, ask, neg, receipts, no_opt, alone, network, bus, ledger, tool)


def _export(twins, agents, weather, grid, ask, neg, receipts, no_opt, alone, network, bus, ledger, tool) -> dict:
    w = ask.window
    after = list(range(max(w) + 1, 24))
    def r1(a):
        return [round(float(x), 1) for x in a]
    members = []
    for t in twins:
        m = t.member_id
        rec = receipts.get(m)
        o = neg.offers.get(m)
        steps = [q for rd in neg.rounds for q in rd["requests"] if q["member"] == m]
        phone = None
        if rec:
            hrs = len(w)
            parts = [f"Your {'home' if t.kind == 'household' else 'building'} helped for {hrs} hours today.",
                     f"Earned ${rec.payment_usd:.2f}."]
            if rec.indoor_f_range:
                parts.append(f"Stayed at {rec.indoor_f_range[0]:.0f}-{rec.indoor_f_range[1]:.0f}°F.")
            if rec.battery_min_pct is not None:
                parts.append(f"Battery stayed above {rec.battery_min_pct:.0f}%.")
            phone = " ".join(parts)
        members.append({
            "id": m, "name": t.display_name, "kind": t.kind, "kind_label": KIND_LABEL[t.kind], "label": t.label,
            "source": t.source, "assets": t.assets, "late_joiner": m == LATE_JOINER,
            "battery": t.battery, "cost_per_kwh": t.cost_per_kwh,
            "offer_window_kw": (min(o.hours[h].can_reduce_kw for h in w) if o else None),
            "steps": steps, "committed_kw": neg.committed.get(m, 0.0),
            "assignment": (neg.assignments[m].model_dump(mode="json") if m in neg.assignments else None),
            "receipt": (rec.model_dump(mode="json") if rec else None), "phone": phone,
            "planned_kw": r1(t.planned_kw), "actual_kw": r1(agents[m].actual_kw()),
            "private": {"owner_limit_kw": agents[m].guard.limits.max_reduce_kw,
                        "comfort_max_c": agents[m].guard.limits.comfort_max_c,
                        "battery_reserve_pct": agents[m].guard.limits.battery_reserve_pct,
                        "load_kw_sample": r1(t.load_kw[16:20])},
        })
    fairness = {}
    for mm in members:
        k = mm["kind_label"]
        f = fairness.setdefault(k, {"members": 0, "earning_members": 0, "usd": 0.0, "kwh": 0.0})
        f["members"] += 1
        if mm["receipt"]:
            f["earning_members"] += 1
            f["usd"] = round(f["usd"] + mm["receipt"]["payment_usd"], 2)
            f["kwh"] = round(f["kwh"] + mm["receipt"]["delivered_kwh"], 1)
    hp_only = [mm for mm in members if mm["kind"] == "household" and not mm["battery"]]
    paid = round(sum(r.payment_usd for r in receipts.values()), 2)
    summary = {
        "peak_kw": {"no_opt": round(float(no_opt.max()), 1), "alone": round(float(alone.max()), 1),
                    "network": round(float(network.max()), 1)},
        "peak_hour": {"no_opt": int(no_opt.argmax()), "alone": int(alone.argmax()), "network": int(network.argmax())},
        "window_kw_mean": {"no_opt": round(float(no_opt[w].mean()), 1), "alone": round(float(alone[w].mean()), 1),
                           "network": round(float(network[w].mean()), 1)},
        "after_window_peak_kw": {"no_opt": round(float(no_opt[after].max()), 1),
                                 "alone": round(float(alone[after].max()), 1),
                                 "network": round(float(network[after].max()), 1)},
        "ask_kw": ask.kw, "pooled_kw": neg.pooled_kw, "delivered_kwh": round(sum(r.delivered_kwh for r in receipts.values()), 1),
        "paid_usd": paid, "members_paid": len(receipts), "rounds": len(neg.rounds),
        "hp_only_homes_paid": sum(1 for mm in hp_only if mm["receipt"]), "hp_only_homes": len(hp_only),
        "ledger": ledger.verify()[1], "stagger": neg.stagger,
    }
    out = {
        "version": __version__, "day": EVENT_DAY, "commons": COMMONS, "tool": tool.name,
        "ask": ask.model_dump(mode="json"), "window_label": hours_label(w), "tou_peak": TOU_PEAK,
        "hours": list(range(24)),
        "series": {"no_opt": r1(no_opt), "alone": r1(alone), "network": r1(network),
                   "lmp_usd_mwh": grid.lmp, "system_load_mw": grid.load_mw,
                   "temp_out_c": r1(weather["temp_out_c"])},
        "members": members, "rounds": neg.rounds, "log": bus.log, "fairness": fairness, "summary": summary,
        "labels": {
            "measured": "HouseZero load and PV; Boston Public Library shape; ISO-NE prices and load; HouseZero weather",
            "simulated": "Office, shop and restaurant loads (ComStock templates on HouseZero weather); homes (homesim)",
            "assumption": "Batteries, school size and PV, comfort costs, the time-of-use peak 4-9 PM, "
                          "price paid = Boston-zone real-time price in the window",
        },
    }
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Run the Commonwatt demo day.")
    p.add_argument("--ask-kw", type=float, default=60.0)
    p.add_argument("--window", type=str, default="17,18", help="local hours, e.g. 17,18 = 5-7 PM")
    p.add_argument("--tool", type=str, default=None, help="module:Class of the model tool")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()
    window = [int(x) for x in args.window.split(",")]
    out = run(args.ask_kw, window, args.tool)
    app = ROOT / "app" / "data"
    app.mkdir(parents=True, exist_ok=True)
    (app / "demo.json").write_text(json.dumps(out, indent=1))
    (app / "demo.js").write_text("window.COMMONWATT = " + json.dumps(out) + ";\n")
    export_schemas(ROOT / "protocol" / "schemas")
    if not args.quiet:
        for e in out["log"]:
            to = f" -> {e['to']}" if e["to"] else ""
            print(f"{e['t']}  {e['from']}{to}  {e['text']}")
    s = out["summary"]
    print(f"\nTool: {out['tool']}")
    print(f"Peak kW  no optimization {s['peak_kw']['no_opt']} at {s['peak_hour']['no_opt']}:00 | "
          f"alone {s['peak_kw']['alone']} at {s['peak_hour']['alone']}:00 | "
          f"network {s['peak_kw']['network']} at {s['peak_hour']['network']}:00")
    print(f"Window mean kW  no opt {s['window_kw_mean']['no_opt']} | alone {s['window_kw_mean']['alone']} | "
          f"network {s['window_kw_mean']['network']}")
    print(f"Pooled {s['pooled_kw']} of {s['ask_kw']} kW in {s['rounds']} rounds; delivered {s['delivered_kwh']} kWh; "
          f"paid ${s['paid_usd']} to {s['members_paid']} members ({s['hp_only_homes_paid']}/{s['hp_only_homes']} "
          f"heat-pump-only homes); {s['ledger']}; stagger {s['stagger']}")
    print(f"Wrote {app / 'demo.js'}")


if __name__ == "__main__":
    main()
