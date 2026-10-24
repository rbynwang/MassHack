"""Coordinator (dispatch agent), one per commons.

It sees agent cards and offers, never meter data or owner limits. For an ask it runs up to three negotiation
rounds (who to ask comes from the model tool's `plan_dispatch`), then staggers each member's preparation and
recovery by valley filling, so the commons' load outside the window stays at or below its no-event peak.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from commonwatt import signing
from commonwatt.network import Bus, Registry
from commonwatt.protocol import AgentCard, Ask, Assignment, Offer, Request, Response
from commonwatt.tools.contract import EnergyModelTool

MAX_ROUNDS = 3
NOTICE_HOUR = 10          # the ask arrives at 10:00; preparation can start then


def hours_label(window: list[int]) -> str:
    def lab(h):
        return f"{(h - 1) % 12 + 1} {'AM' if h < 12 else 'PM'}"
    return f"{lab(min(window))} to {lab(max(window) + 1)}"


@dataclass
class Negotiation:
    ask: Ask
    offers: dict[str, Offer] = field(default_factory=dict)
    committed: dict[str, float] = field(default_factory=dict)
    last_response: dict[str, Response] = field(default_factory=dict)
    excluded: set[str] = field(default_factory=set)
    rounds: list[dict] = field(default_factory=list)
    assignments: dict[str, Assignment] = field(default_factory=dict)
    deferred_kwh: float = 0.0
    stagger: dict = field(default_factory=dict)

    @property
    def pooled_kw(self) -> float:
        return round(sum(self.committed.values()), 2)


class Coordinator:
    def __init__(self, commons: str, bus: Bus, registry: Registry, tool: EnergyModelTool) -> None:
        self.id = "coordinator"
        self.commons = commons
        self.keys = signing.KeyPair()
        self.bus, self.registry, self.tool = bus, registry, tool
        self._req = 0

    def card(self) -> AgentCard:
        return AgentCard(agent_id=self.id, role="coordinator", display_name="Commons coordinator",
                         owner="Cambridge commons steward", commons=self.commons, public_key=self.keys.public_hex)

    # ------------------------------------------------------------ rounds
    def run_round(self, neg: Negotiation, round_no: int, agents: dict) -> dict:
        ask = neg.ask
        need = round(ask.kw - neg.pooled_kw, 2)
        offers = [neg.offers[c.agent_id] for c in self.registry.members(self.commons) if c.agent_id in neg.offers]
        allocs = self.tool.plan_dispatch(offers, need, ask.window, ask.price_usd_per_kwh, round_no,
                                         neg.excluded, neg.committed)
        summary = {"round": round_no, "need_kw": need, "requests": []}
        self.bus.note(self.id, f"Round {round_no}: {need:.1f} kW still needed, asking {len(allocs)} members",
                      kind="round")
        for a in allocs:
            m = a.member_id
            total = round(neg.committed.get(m, 0.0) + a.reduce_kw, 2)
            self._req += 1
            req = Request(request_id=f"q{self._req:03d}", ask_id=ask.ask_id, member_id=m, round=round_no,
                          reduce_kw=total, window=ask.window, price_usd_per_kwh=ask.price_usd_per_kwh)
            ag = agents[m]
            self.bus.send(self.id, self.keys, f"guard:{m}", req, f"Request {m}: minus {total:.1f} kW")
            resp = ag.on_request(req)
            if resp.decision == "blocked":
                self.bus.send(f"guard:{m}", ag.guard.keys, self.id, resp,
                              f"Blocked: request to {m} {resp.reason.removeprefix('trust guard: ')}")
            else:
                self.bus.send(f"guard:{m}", ag.guard.keys, m, req, "Request (within limits)")
                text = {"accept": "Accept", "decline": "Decline", "counter": f"Counter: minus {resp.kw:.1f} kW"}
                self.bus.send(m, ag.keys, self.id, resp, f"{text[resp.decision]} ({resp.reason})")
            if resp.decision in ("accept", "counter"):
                neg.committed[m] = resp.kw
                neg.last_response[m] = resp
            if resp.decision != "accept":
                neg.excluded.add(m)
            summary["requests"].append({"member": m, "asked_kw": total, "decision": resp.decision,
                                        "kw": resp.kw, "reason": resp.reason})
        summary["pooled_kw"] = neg.pooled_kw
        neg.rounds.append(summary)
        return summary

    # ------------------------------------------------------------ staggering
    def stagger(self, neg: Negotiation) -> None:
        """Valley-fill each member's schedulable preparation and recovery energy."""
        w = neg.ask.window
        offers = list(neg.offers.values())
        planned = np.array([sum(o.hours[h].planned_kw for o in offers) for h in range(24)])
        load = planned.copy()
        for m, kw in neg.committed.items():
            load[w] -= kw
            for h, v in neg.last_response[m].fixed_kw.items():
                load[int(h)] += v
        prep_hours = list(range(NOTICE_HOUR, min(w)))
        rec_hours = list(range(max(w) + 1, 24))
        cap_prep = float(planned.max())
        cap_rec = float(planned[rec_hours].max())
        prep_kw = {m: {} for m in neg.committed}
        rec_kw = {m: {} for m in neg.committed}

        def fill(member: str, energy: float, hours: list[int], cap: float, max_kw: float, out: dict) -> float:
            step = 0.25
            while energy > 1e-6:
                cand = [h for h in hours if out.get(h, 0.0) < max_kw - 1e-9 and load[h] < cap - 1e-9]
                if not cand:
                    return energy
                h = min(cand, key=lambda x: load[x])
                d = min(step, energy, max_kw - out.get(h, 0.0), cap - load[h])
                out[h] = out.get(h, 0.0) + d
                load[h] += d
                energy -= d
            return 0.0

        order = sorted(neg.committed, key=lambda m: -neg.last_response[m].rebound_kwh)
        unplaced_prep = 0.0
        for m in order:
            r = neg.last_response[m]
            unplaced_prep += fill(m, r.prep_kwh, prep_hours, cap_prep, r.max_recovery_kw or 1e9, prep_kw[m])
        deferred = 0.0
        for m in order:
            r = neg.last_response[m]
            deferred += fill(m, r.rebound_kwh, rec_hours, cap_rec, r.max_recovery_kw or 1e9, rec_kw[m])
        neg.deferred_kwh = round(float(deferred), 1)
        neg.stagger = {"cap_after_kw": round(cap_rec, 1), "cap_before_kw": round(cap_prep, 1),
                       "unplaced_prep_kwh": round(float(unplaced_prep), 2),
                       "deferred_to_overnight_kwh": neg.deferred_kwh}
        for m, kw in neg.committed.items():
            neg.assignments[m] = Assignment(
                ask_id=neg.ask.ask_id, member_id=m, reduce_kw=kw, window=w,
                prep_kw={h: round(v, 3) for h, v in prep_kw[m].items()},
                recovery_kw={h: round(v, 3) for h, v in rec_kw[m].items()},
                price_usd_per_kwh=neg.ask.price_usd_per_kwh)
