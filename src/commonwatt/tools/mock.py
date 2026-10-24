"""MockModelTool: a labeled stand-in for the trained model, until it is plugged in.

Member side: reads the member's digital twin (`ctx.twin`, see members.py). Its forecast is the twin's own day,
so it is a perfect-foresight stand-in (labeled as such in the demo). Flexibility and decisions come from the
twin's physics: battery power and energy limits, the one-node thermal model and comfort band for homes, the
pre-cool mode in the training data for businesses, and a labeled HVAC rule for public buildings.

Coordinator side: round 1 asks the cheapest offers first, each for what it offered per hour; members that cannot
hold that for the whole window counter. Later rounds spread the remaining gap pro rata over every member with
capacity left (including members that joined after round 1), so small members such as heat-pump-only homes are
included rather than crowded out.
"""

from __future__ import annotations

import numpy as np

from commonwatt.tools.contract import Allocation, Decision, Flexibility, Forecast, MemberContext

ROUND1_MARGIN = 0.10   # later rounds ask 10 % more than the gap, to cover counters and declines


def _floor2(x: float) -> float:
    """Round down to 0.01 kW, so a rounded promise is never more than the member can hold."""
    return float(np.floor(x * 100 + 1e-9) / 100)


class MockModelTool:
    name = "mock (perfect-foresight twin + rules)"

    # ------------------------------------------------------------ member side
    def forecast(self, ctx: MemberContext, horizon_h: int = 24) -> Forecast:
        tw = ctx.twin
        net = tw.planned_kw
        band = 0.08 * np.abs(net) + 0.05
        return Forecast(hours=list(range(horizon_h)), load_kw=tw.load_kw.round(3).tolist(),
                        pv_kw=tw.pv_kw.round(3).tolist(), net_kw=net.round(3).tolist(),
                        net_p10_kw=(net - band).round(3).tolist(), net_p90_kw=(net + band).round(3).tolist(),
                        method="perfect-foresight stand-in (the twin's own day)")

    def flexibility(self, ctx: MemberContext, window: list[int]) -> Flexibility:
        c = ctx.twin.capability(window)
        return Flexibility(window=window, can_reduce_kw=c["per_hour"], can_increase_kw=c["increase"],
                           sustain_reduce_kw=c["sustain"], prep_kwh_per_kwh=c["prep_ratio"],
                           rebound_kwh_per_kwh=c["rebound_ratio"], max_recovery_kw=c["max_recovery_kw"],
                           cost_per_kwh=ctx.twin.cost_per_kwh, method="twin physics")

    def decide(self, ctx: MemberContext, reduce_kw: float, window: list[int], price: float) -> Decision:
        tw = ctx.twin
        if price < tw.cost_per_kwh:
            return Decision("decline", 0.0, f"price ${price:.2f}/kWh is below my cost ${tw.cost_per_kwh:.2f}/kWh")
        p = tw.plan(reduce_kw, window)
        predicted = {}
        if p.indoor_c is not None:
            predicted["indoor_c_range"] = [round(float(p.indoor_c.min()), 2), round(float(p.indoor_c.max()), 2)]
        if p.battery_min_pct is not None:
            predicted["battery_min_pct"] = round(p.battery_min_pct, 1)
        predicted["fixed_kw"] = {int(h): round(float(v), 3) for h, v in enumerate(p.fixed_delta_kw)
                                 if abs(v) > 1e-3 and h not in window}
        args = dict(prep_kwh=round(p.battery_prep_kwh, 3), rebound_kwh=round(p.battery_recovery_kwh, 3),
                    max_recovery_kw=p.battery_max_kw, predicted=predicted)
        if p.kw >= reduce_kw - 0.01:
            return Decision("accept", _floor2(min(reduce_kw, p.kw + 0.01)), "within my limits for the whole window",
                            **args)
        if p.kw >= 0.1:
            what = "battery energy" if p.battery_kw > 0 and p.thermal_kw < 0.05 else "comfort band"
            return Decision("counter", _floor2(p.kw),
                            f"I can hold {_floor2(p.kw):.1f} kW for all {len(window)} h ({what})", **args)
        return Decision("decline", 0.0, "no flexibility left in this window")

    # ------------------------------------------------------------ coordinator side
    def plan_dispatch(self, offers, need_kw, window, price, round_no, exclude, committed):
        avail = {}
        for o in offers:              # every member is asked; each one decides for itself on the posted price
            if o.member_id in exclude:
                continue
            hours = {x.hour: x for x in o.hours}
            a = min(hours[h].can_reduce_kw for h in window) - committed.get(o.member_id, 0.0)
            if a > 0.1:
                avail[o.member_id] = a
        total = sum(avail.values())
        if need_kw <= 0 or total <= 0:
            return []
        if round_no == 1:                       # merit order: cheapest offers first, each for its full offer
            cost = {o.member_id: o.cost_per_kwh for o in offers}
            out, acc = [], 0.0
            for m in sorted(avail, key=lambda x: (cost[x], -avail[x])):
                if acc >= need_kw - 0.01:
                    break
                kw = _floor2(min(avail[m], need_kw - acc))
                if kw >= 0.1:
                    out.append(Allocation(m, kw, "cheapest first"))
                    acc += kw
            return out
        target = need_kw * (1 + ROUND1_MARGIN)
        share = min(1.0, target / total)
        out = [Allocation(m, round(share * a, 2), f"{share:.0%} of what is left") for m, a in avail.items()
               if share * a >= 0.1]
        if sum(x.reduce_kw for x in out) < need_kw:     # a small gap: give it to the member with most room
            m = max(avail, key=avail.get)
            out = [x for x in out if x.member_id != m] + [Allocation(m, round(min(avail[m], target), 2), "top-up")]
        return out
