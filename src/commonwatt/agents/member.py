"""Member agent: one per building. Holds its own data, calls the model tool, and decides for itself.

Requests reach it only through its trust guard. It answers accept, counter (with what it can hold for the whole
window) or decline. Only offers and responses leave the agent; meter data and owner limits stay inside.
"""

from __future__ import annotations

import pandas as pd

from commonwatt import signing
from commonwatt.members import Twin
from commonwatt.protocol import AgentCard, Ask, Assignment, Envelope, Offer, OfferHour, Request, Response
from commonwatt.tools.contract import EnergyModelTool, MemberContext
from commonwatt.trust import Ledger, OwnerLimits, TrustGuard


class MemberAgent:
    def __init__(self, twin: Twin, tool: EnergyModelTool, commons: str, limits: OwnerLimits, ledger: Ledger,
                 weather: pd.DataFrame) -> None:
        self.twin = twin
        self.id = twin.member_id
        self.tool = tool
        self.commons = commons
        self.keys = signing.KeyPair()
        self.guard = TrustGuard(self.id, limits, ledger)
        hist = twin.history if getattr(twin, "history", None) is not None else pd.DataFrame(
            columns=["load_kw", "pv_kw", "net_kw", "temp_out_c"])
        self.ctx = MemberContext(member_id=self.id, kind=twin.kind, as_of_local="2025-06-24 10:00", history=hist,
                                 weather_today=weather[["temp_out_c", "solar_w_m2"]],
                                 assets={"battery": twin.battery, "assets": twin.assets}, twin=twin)
        self.decision = None
        self.assignment: Assignment | None = None

    # ------------------------------------------------------------ protocol
    def card(self) -> AgentCard:
        t = self.twin
        return AgentCard(agent_id=self.id, role="member", kind=t.kind, display_name=t.display_name, owner=t.owner,
                         commons=self.commons, assets=t.assets,
                         can_offer=["reduce", "increase"] if t.battery else ["reduce"],
                         public_key=self.keys.public_hex, guard_public_key=self.guard.keys.public_hex,
                         data_label=t.label)

    def make_offer(self, ask: Ask) -> Offer:
        fc = self.tool.forecast(self.ctx)
        fl = self.tool.flexibility(self.ctx, ask.window)
        hours = [OfferHour(hour=h, planned_kw=round(fc.net_kw[h], 2),
                           can_reduce_kw=round(fl.can_reduce_kw.get(h, 0.0), 2),
                           can_increase_kw=round(fl.can_increase_kw.get(h, 0.0), 2)) for h in range(24)]
        return Offer(ask_id=ask.ask_id, member_id=self.id, hours=hours, cost_per_kwh=fl.cost_per_kwh,
                     prep_kwh_per_kwh=fl.prep_kwh_per_kwh, rebound_kwh_per_kwh=fl.rebound_kwh_per_kwh,
                     max_recovery_kw=fl.max_recovery_kw)

    def guard_card(self) -> AgentCard:
        return AgentCard(agent_id=f"guard:{self.id}", role="guard", display_name=f"Trust guard of {self.id}",
                         owner=self.twin.owner, commons=self.commons, public_key=self.guard.keys.public_hex)

    def on_request(self, req: Request) -> Response:
        verdict = self.guard.check_request(req)           # the guard runs before the agent sees the request
        if not verdict.ok:
            return Response(request_id=req.request_id, member_id=self.id, decision="blocked", kw=0.0,
                            reason=f"trust guard: {verdict.reason}")
        d = self.tool.decide(self.ctx, req.reduce_kw, req.window, req.price_usd_per_kwh)
        if d.decision in ("accept", "counter"):
            plan_ok = self.guard.check_plan(d.predicted)
            if not plan_ok.ok:
                return Response(request_id=req.request_id, member_id=self.id, decision="decline", kw=0.0,
                                reason=f"trust guard: {plan_ok.reason}")
            self.decision = d
        fixed = {int(h): v for h, v in d.predicted.get("fixed_kw", {}).items()}
        return Response(request_id=req.request_id, member_id=self.id, decision=d.decision, kw=d.kw,
                        reason=d.reason, prep_kwh=d.prep_kwh, rebound_kwh=d.rebound_kwh,
                        max_recovery_kw=d.max_recovery_kw, fixed_kw=fixed)

    def on_assignment(self, env: Envelope) -> None:
        self.assignment = Assignment(**env.body)

    # ------------------------------------------------------------ the day itself
    def actual_kw(self):
        """Metered draw for the day under its assignment (no assignment = its own plan)."""
        if self.assignment is None or self.decision is None:
            return self.twin.planned_kw.copy()
        a = self.assignment
        plan = self.decision.predicted["plan"]
        return self.twin.execute(plan, a.window, a.prep_kw, a.recovery_kw)

    def indoor_f(self) -> list[float] | None:
        if self.twin.home is None:
            return None
        tin = self.decision.predicted["plan"].indoor_c if self.decision else self.twin.indoor_baseline_c()
        occupied = tin[7:23]
        return [round(float(occupied.min()) * 9 / 5 + 32, 1), round(float(occupied.max()) * 9 / 5 + 32, 1)]
