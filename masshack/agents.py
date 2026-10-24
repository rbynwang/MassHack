"""Member agents. Every member: ML load forecast -> own battery plan -> hourly flex offers with cost.

Prosumer agents (Massachusetts buildings with solar + battery and their own meter data) offer battery flex.
Flex members (small businesses and renters without batteries) offer building-mode flex (load shift, pre-cool,
pre-heat, short HVAC curtail) and must disclose the rebound that comes with it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .physics import Battery, Tariff
from .optimizer import optimize_battery
from .coordinator import Offer
from .trust import Limits

COMFORT_USD_PER_KWH = 0.08     # assumption: what shifting 1 kWh of HVAC costs a member in comfort/attention


@dataclass
class MemberAgent:
    member_id: str
    role: str                         # "prosumer" or "flex"
    building_type: str
    sqft: float
    zip: str
    source: str
    tariff: Tariff
    battery: Battery | None = None
    pv_kwdc: float = 0.0
    modes: list = field(default_factory=lambda: ["baseline"])
    limits: Limits | None = None
    # filled each day
    fc: pd.DataFrame | None = None
    pv_fc: np.ndarray | None = None
    plan: dict | None = None
    mode_fc: dict = field(default_factory=dict)

    # 1. forecast ---------------------------------------------------------------------------
    def forecast_day(self, forecaster, day_start, weather_fc):
        self.fc = forecaster.forecast(self.member_id, day_start, "baseline", weather_fc)
        self.pv_fc = (weather_fc["pv_per_kwdc"].fillna(0).values * self.pv_kwdc) if self.pv_kwdc else np.zeros(len(self.fc))
        self.mode_fc = {}
        for m in self.modes:
            if m != "baseline":
                try:
                    self.mode_fc[m] = forecaster.forecast(self.member_id, day_start, m, weather_fc)["p50"].values
                except Exception:
                    pass
        return self.fc

    # 2. own plan ---------------------------------------------------------------------------
    def plan_day(self, prior_peak_kw: float, dt: float = 1.0, use_p90_peak: bool = True, price=None, import_cap=None):
        load = self.fc["p50"].values
        if self.battery is None:
            net = load - self.pv_fc
            self.plan = {"ok": True, "import_kw": np.clip(net, 0, None), "export_kw": np.clip(-net, 0, None),
                         "charge_kw": np.zeros_like(net), "discharge_kw": np.zeros_like(net), "soc": None,
                         "objective_usd": float(np.clip(net, 0, None).sum() * dt * self.tariff.energy_usd_per_kwh)}
            return self.plan
        # plan against a cautious load (P50 for energy, but protect the P90 peak)
        planning_load = np.maximum(load, self.fc["p90"].values * 0.9) if use_p90_peak else load
        self.plan = optimize_battery(planning_load, self.pv_fc, self.battery, self.tariff, dt=dt, prior_peak_kw=prior_peak_kw,
                                     price_usd_per_kwh=price, import_cap=import_cap)
        if not self.plan.get("ok") and import_cap:      # cap not reachable with this battery: plan without it
            self.plan = optimize_battery(planning_load, self.pv_fc, self.battery, self.tariff, dt=dt, prior_peak_kw=prior_peak_kw,
                                         price_usd_per_kwh=price)
        self.plan["price"] = price
        self.plan["prior_peak_kw"] = prior_peak_kw
        self.plan["planning_load"] = planning_load
        return self.plan

    # 3. offers -----------------------------------------------------------------------------
    def offers(self, signal_hours: list[tuple[int, str]], dt: float = 1.0) -> list[Offer]:
        out = []
        for h, kind in signal_hours:
            if self.battery is not None and self.plan and self.plan.get("ok"):
                out += self._battery_offer(h, kind, dt)
            if self.role == "flex" or self.mode_fc:
                out += self._mode_offers(h, kind, dt)
        return out

    def _battery_offer(self, h, kind, dt):
        p = self.plan
        net = p["import_kw"] - p["export_kw"]
        e_now = (p["soc"][h - 1] if h > 0 else self.battery.soc0) * self.battery.capacity_kwh
        lim = self.limits
        if kind == "use_less":
            room_power = self.battery.power_kw - p["discharge_kw"][h] + p["charge_kw"][h]
            e_after_plan = float(p["soc"][h]) * self.battery.capacity_kwh          # stored energy after this hour's own plan
            room_energy = (e_after_plan - lim.min_soc * self.battery.capacity_kwh) * self.battery.eta_discharge / dt
            kw = max(0.0, min(room_power, room_energy, lim.max_down_kw, max(net[h], 0) + p["export_kw"][h] + room_power))
            delta = -kw
        else:
            room_power = self.battery.power_kw - p["charge_kw"][h] + p["discharge_kw"][h]
            room_energy = (self.battery.e_max - float(p["soc"][h]) * self.battery.capacity_kwh) / (self.battery.eta_charge * dt)
            kw = max(0.0, min(room_power, room_energy, lim.max_up_kw))
            delta = kw
        if kw < 0.05:
            return []
        forced = optimize_battery(p["planning_load"], self.pv_fc, self.battery, self.tariff, dt=dt, price_usd_per_kwh=p.get("price"),
                                  prior_peak_kw=p["prior_peak_kw"], forced_import_delta={h: delta}, base_import=net)
        if not forced.get("ok"):
            kw *= 0.5
            forced = optimize_battery(p["planning_load"], self.pv_fc, self.battery, self.tariff, dt=dt, price_usd_per_kwh=p.get("price"),
                                      prior_peak_kw=p["prior_peak_kw"], forced_import_delta={h: np.sign(delta) * kw}, base_import=net)
            if not forced.get("ok"):
                return []
        cost = max(forced["objective_usd"] - p["objective_usd"], 0.0)
        return [Offer(self.member_id, h, kind, kw, cost + 0.02 * kw, "battery")]

    def _mode_offers(self, h, kind, dt):
        out = []
        base = self.fc["p50"].values
        for mode, prof in self.mode_fc.items():
            if mode == "precool_42":
                continue    # pre-cooling raised the midday peak in the data and in practice: members do not offer it
            diff = prof - base                    # negative = mode uses less
            if kind == "use_less" and diff[h] < -0.05:
                kw = min(-diff[h], self.limits.max_down_kw)
            elif kind == "soak_up" and diff[h] > 0.05:
                kw = min(diff[h], self.limits.max_up_kw)
            else:
                continue
            if prof.max() > base.max() + 0.02 * max(base.max(), 1e-6):
                continue    # self-interested: never offer a mode that raises my own monthly peak (pre-cool often does)
            rebound = diff.copy(); rebound[h] = 0.0
            shifted = float(np.abs(diff).sum() * dt / 2)
            bill_delta = float((np.clip(prof - self.pv_fc, 0, None) - np.clip(base - self.pv_fc, 0, None)).sum() * dt * self.tariff.energy_usd_per_kwh)
            peak_pen = max(prof.max() - base.max(), 0) * self.tariff.demand_usd_per_kw
            cost = max(bill_delta, 0) + peak_pen + COMFORT_USD_PER_KWH * shifted
            out.append(Offer(self.member_id, h, kind, kw, cost, mode, rebound_kw=rebound))
        return out


def default_limits(role: str, battery: Battery | None, peak_kw: float) -> Limits:
    if battery is not None:
        return Limits(max_down_kw=battery.power_kw, max_up_kw=battery.power_kw, min_soc=0.20)
    return Limits(max_down_kw=0.25 * peak_kw, max_up_kw=0.15 * peak_kw, min_soc=0.0)


RESIDENTIAL_TARIFF = Tariff(tariff_id="residential_flat", energy_usd_per_kwh=0.30, demand_usd_per_kw=0.0, fixed_usd_per_month=10.0,
                            export_credit_usd_per_kwh=0.10, source="assumption: Massachusetts residential flat rate, no demand charge")


def build_agents(ds, tariff: Tariff, community_only: bool = True) -> dict:
    """One agent per community member, configured from members.csv: role, battery, solar, reserve, modes, tariff.

    Prosumers (solar + battery, own meter data) offer battery flex; flex members (small businesses, renters, homes
    without batteries) offer building modes or EV delay. Rules a member sets (battery reserve, cooling-center duty,
    no building-mode control) become trust-layer limits.
    """
    agents = {}
    M = ds.members
    if community_only and "in_community" in M:
        M = M[M["in_community"].astype(str).str.lower().isin(["true", "1"])]
    for mid, r in M.iterrows():
        series = ds.series(mid)
        peak = float(np.nanmax(series.values)) if series.notna().any() else 0.0
        role = str(r.get("role", "flex")) if isinstance(r.get("role", None), str) else "flex"
        bat = None
        pv = float(r.get("pv_kwdc", 0) or 0) if role == "prosumer" else 0.0
        cap, pkw = float(r.get("battery_kwh", 0) or 0), float(r.get("battery_kw", 0) or 0)
        min_soc = float(r.get("min_soc", 0.2) or 0.2)
        if role == "prosumer":
            if cap <= 0 or pkw <= 0:
                cap, pkw = 2 * 0.30 * peak, 0.30 * peak
            bat = Battery(capacity_kwh=cap, power_kw=pkw, soc0=max(0.5, min(min_soc + 0.1, 0.9)))
        allow = str(r.get("allow_building_modes", True)).lower() in ("true", "1")
        modes = [m for m in ds.modes(mid) if m == "baseline" or allow]
        lim = default_limits(role, bat, peak)
        lim.min_soc = min_soc if bat is not None else 0.0
        lim.allow_building_modes = allow
        t = RESIDENTIAL_TARIFF if str(r.get("tariff_id", "")) == "residential_flat" else tariff
        ag = MemberAgent(mid, role, str(r.get("building_type", "unknown")), float(r.get("sqft", 0) or 0),
                         str(r.get("zip", "")), str(r.get("source", "")), t, bat, pv, modes, lim)
        ag.group = str(r.get("group", ""))
        ag.cooling_center = str(r.get("cooling_center", False)).lower() in ("true", "1")
        ag.base_min_soc = lim.min_soc
        agents[mid] = ag
    return agents
