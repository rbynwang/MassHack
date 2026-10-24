"""Collective coordinator: turns grid signals into tasks and assigns them across members.

Grid -> coordinator: each hour is `use_less` (grid stress, price spike or a demand-response event),
`soak_up` (cheap or negative price while members export surplus solar) or `normal`.
Coordinator -> members: pools every member's offer and buys the cheapest kW first (merit order), then checks
with the forecast that the assignment does not create a new community peak through rebound.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Offer:
    member_id: str
    hour_index: int
    direction: str          # "use_less" or "soak_up"
    kw: float               # most it can deliver beyond its own plan
    cost_usd: float         # what delivering `kw` costs the member (lost bill savings + comfort)
    source: str             # "battery" or building mode
    rebound_kw: np.ndarray | None = None   # change in load at later hours if accepted (building modes)

    @property
    def usd_per_kw(self) -> float:
        return self.cost_usd / self.kw if self.kw > 1e-9 else float("inf")


@dataclass
class Signal:
    hour_index: int
    kind: str               # use_less / soak_up / normal
    target_kw: float
    value_usd_per_kw: float  # what the grid pays per kW delivered this hour
    reasons: list


def grid_signals(hours_local, lmp_usd_mwh, system_load_mw, dr_event, community_import_kw, community_export_kw,
                 stress_q: float = 0.95, cheap_q: float = 0.10, target_share: float = 0.15,
                 dr_usd_per_kw_event: float = 5.0) -> list[Signal]:
    """Classify each hour. Thresholds are quantiles over the whole 2025-26 year, passed in as arrays."""
    sig = []
    lmp = np.asarray(lmp_usd_mwh, float)
    load = np.asarray(system_load_mw, float)
    hi_load = np.nanquantile(load, stress_q)
    hi_price = np.nanquantile(lmp, stress_q)
    lo_price = np.nanquantile(lmp, cheap_q)
    for i, _ in enumerate(hours_local):
        reasons = []
        if dr_event[i]:
            reasons.append("demand-response event")
        if load[i] >= hi_load:
            reasons.append("ISO-NE load in top 5%")
        if lmp[i] >= hi_price:
            reasons.append("price spike")
        if reasons:
            value = dr_usd_per_kw_event if dr_event[i] else max(lmp[i], 0) / 1000.0
            sig.append(Signal(i, "use_less", target_share * community_import_kw[i], value, reasons))
        elif (lmp[i] <= lo_price or lmp[i] < 0) and community_export_kw[i] > 0:
            sig.append(Signal(i, "soak_up", community_export_kw[i], max(-lmp[i], 0) / 1000.0 + 0.02,
                              ["cheap or negative price", "community exporting surplus solar"]))
        else:
            sig.append(Signal(i, "normal", 0.0, 0.0, []))
    return sig


def assign(offers: list[Offer], signal: Signal, community_forecast_kw: np.ndarray, current_peak_kw: float):
    """Merit order with a rebound check. Returns (accepted [(offer, kw)], rejected [(offer, reason)])."""
    accepted, rejected = [], []
    if signal.kind == "normal" or signal.target_kw <= 0:
        return accepted, rejected
    remaining = signal.target_kw
    projected = np.asarray(community_forecast_kw, float).copy()
    for off in sorted([o for o in offers if o.direction == signal.kind and o.kw > 1e-6], key=lambda o: o.usd_per_kw):
        if remaining <= 1e-6:
            break
        if off.usd_per_kw > signal.value_usd_per_kw + 0.05:
            rejected.append((off, "costs more than the grid pays"))
            continue
        take = min(off.kw, remaining)
        trial = projected.copy()
        sign = -1 if signal.kind == "use_less" else 1
        trial[signal.hour_index] += sign * take
        if off.rebound_kw is not None:
            trial += off.rebound_kw * (take / off.kw)
        if signal.kind == "use_less" and trial.max() > max(current_peak_kw, projected.max()) + 1e-6:
            rejected.append((off, f"rebound would set a new community peak ({trial.max():.1f} kW)"))
            continue
        projected = trial
        accepted.append((off, take))
        remaining -= take
    return accepted, rejected


def split_revenue(delivered: dict, revenue_usd: float, member_costs: dict) -> dict:
    """Pro rata to delivered kW, after reimbursing each member's own cost. delivered: {member: kW}."""
    total = sum(delivered.values())
    if total <= 0:
        return {m: 0.0 for m in delivered}
    costs = sum(member_costs.get(m, 0.0) for m in delivered)
    if revenue_usd < costs:   # never pay out more than the grid paid: reimburse costs pro rata
        return {m: revenue_usd * member_costs.get(m, 0.0) / costs if costs > 0 else 0.0 for m in delivered}
    surplus = revenue_usd - costs
    return {m: member_costs.get(m, 0.0) + surplus * kw / total for m, kw in delivered.items()}
