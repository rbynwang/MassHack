"""Exact battery physics and bill math. Never learned.

All power in kW, energy in kWh, money in USD. `dt` is the step length in hours.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import numpy as np


@dataclass
class Battery:
    capacity_kwh: float
    power_kw: float
    eta_charge: float = 0.95          # one-way; round trip ~0.90
    eta_discharge: float = 0.95
    soc_min: float = 0.10             # fraction of capacity
    soc_max: float = 0.95
    soc0: float = 0.50

    @property
    def e_min(self) -> float:
        return self.capacity_kwh * self.soc_min

    @property
    def e_max(self) -> float:
        return self.capacity_kwh * self.soc_max

    def step(self, energy_kwh: float, charge_kw: float, discharge_kw: float, dt: float) -> float:
        """Advance stored energy one step, clipping to physical limits."""
        e = energy_kwh + (self.eta_charge * charge_kw - discharge_kw / self.eta_discharge) * dt
        return float(np.clip(e, self.e_min, self.e_max))


@dataclass
class Tariff:
    """Small commercial tariff: energy charge + monthly demand charge on the highest interval kW."""
    tariff_id: str = "ma_g2_example"
    energy_usd_per_kwh: float = 0.18341
    demand_usd_per_kw: float = 10.56
    fixed_usd_per_month: float = 90.0
    export_credit_usd_per_kwh: float = 0.10   # assumption: net-metering style credit below retail
    min_billing_kw: float = 0.0
    source: str = "Town of Concord MA G-2, effective 2026-04-01 (OpenEI URDB); export credit is an assumption"

    @classmethod
    def from_json(cls, path: str | Path, key: str = "ma_g2_example") -> "Tariff":
        d = json.loads(Path(path).read_text())
        d = d.get(key, d)
        fields = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**fields)


def bill(grid_import_kw: np.ndarray, grid_export_kw: np.ndarray, tariff: Tariff, dt: float,
         months: int = 1, prior_peak_kw: float = 0.0) -> dict:
    """Bill for one billing period (or a slice of one).

    prior_peak_kw: the month's peak so far, so a single day is billed only for raising it.
    Returns a breakdown in USD.
    """
    imp = np.asarray(grid_import_kw, float)
    exp = np.asarray(grid_export_kw, float)
    energy = float(imp.sum() * dt * tariff.energy_usd_per_kwh)
    credit = float(exp.sum() * dt * tariff.export_credit_usd_per_kwh)
    peak = max(float(imp.max(initial=0.0)), tariff.min_billing_kw)
    demand = max(peak - prior_peak_kw, 0.0) * tariff.demand_usd_per_kw
    return {
        "energy_usd": energy,
        "export_credit_usd": credit,
        "demand_usd": demand,
        "fixed_usd": tariff.fixed_usd_per_month * months,
        "peak_kw": peak,
        "total_usd": energy - credit + demand + tariff.fixed_usd_per_month * months,
    }


def settle_flows(load_kw: np.ndarray, pv_kw: np.ndarray, charge_kw: np.ndarray, discharge_kw: np.ndarray):
    """Grid import/export from a power balance: load - pv + charge - discharge = import - export."""
    net = np.asarray(load_kw) - np.asarray(pv_kw) + np.asarray(charge_kw) - np.asarray(discharge_kw)
    return np.clip(net, 0, None), np.clip(-net, 0, None)


def peak_guard(battery: Battery, load_kw, pv_kw, plan_charge, plan_discharge, cap_kw: float, dt: float,
               committed=None, e0: float | None = None):
    """Real-time controller that follows the plan's intent but reacts to the ACTUAL load.

    - never charges in a way that pushes import above the planned peak (cap)
    - discharges whatever is needed to keep import at or below the cap
    - in hours committed to the collective, delivers at least the committed discharge
    This is how a deployed battery behaves: the plan sets the peak target, the controller enforces it.
    """
    n = len(load_kw)
    committed = np.zeros(n, bool) if committed is None else np.asarray(committed, bool)
    e = battery.capacity_kwh * battery.soc0 if e0 is None else e0
    c_real, d_real, soc = np.zeros(n), np.zeros(n), np.zeros(n)
    for t in range(n):
        base = load_kw[t] - pv_kw[t]
        c = max(plan_charge[t], 0.0)
        c = min(c, max(cap_kw - base, 0.0)) if base + c > cap_kw else c          # no charging over the cap
        need = max(base + c - cap_kw, 0.0)                                         # shave to the cap
        d = max(need, plan_discharge[t]) if committed[t] else need
        if base - d < 0 and not committed[t]:                                      # do not discharge into export
            d = max(base, 0.0)
        c = min(c, battery.power_kw, (battery.e_max - e) / (battery.eta_charge * dt))
        d = min(d, battery.power_kw, (e - battery.e_min) * battery.eta_discharge / dt)
        if c > 0 and d > 0:
            c, d = (c - d, 0.0) if c >= d else (0.0, d - c)
        e = battery.step(e, c, d, dt)
        c_real[t], d_real[t], soc[t] = c, d, e / battery.capacity_kwh
    imp, exp = settle_flows(load_kw, pv_kw, c_real, d_real)
    return {"charge_kw": c_real, "discharge_kw": d_real, "soc": soc, "import_kw": imp, "export_kw": exp, "e_end": e}


def simulate_schedule(battery: Battery, load_kw, pv_kw, charge_kw, discharge_kw, dt: float, e0: float | None = None):
    """Apply a charge/discharge schedule with physics clipping. Returns realized arrays."""
    n = len(load_kw)
    e = battery.capacity_kwh * battery.soc0 if e0 is None else e0
    c_real, d_real, soc = np.zeros(n), np.zeros(n), np.zeros(n)
    for t in range(n):
        c = min(max(charge_kw[t], 0.0), battery.power_kw, (battery.e_max - e) / (battery.eta_charge * dt))
        d = min(max(discharge_kw[t], 0.0), battery.power_kw, (e - battery.e_min) * battery.eta_discharge / dt)
        if c > 0 and d > 0:  # never both
            if c >= d:
                c, d = c - d, 0.0
            else:
                c, d = 0.0, d - c
        e = battery.step(e, c, d, dt)
        c_real[t], d_real[t], soc[t] = c, d, e / battery.capacity_kwh
    imp, exp = settle_flows(load_kw, pv_kw, c_real, d_real)
    return {"charge_kw": c_real, "discharge_kw": d_real, "soc": soc, "import_kw": imp, "export_kw": exp, "e_end": e}
