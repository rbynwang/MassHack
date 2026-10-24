"""Battery and tariff physics — exact equations, never learned.

Units
-----
- Power : kW  (positive = charging from grid/PV, negative = discharging)
- Energy : kWh
- SOC   : kWh  (state-of-charge; not a fraction)

Eversource MA time-of-use tariff (approximation for demo).
Rates are $/kWh.  Peak window is 16:00–21:00 ET on weekdays.
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Battery parameters (Harvard CGBC HouseZero demo assumptions)
# ---------------------------------------------------------------------------
CAPACITY_KWH: float = 13.5       # usable capacity (LFP cell, e.g. Tesla Powerwall 2)
MAX_POWER_KW: float = 5.0        # charge / discharge power limit
ROUND_TRIP_EFF: float = 0.92     # √η applied to each half of the round trip
SOC_MIN_KWH: float = 0.0
SOC_MAX_KWH: float = CAPACITY_KWH

CHARGE_EFF: float = ROUND_TRIP_EFF ** 0.5
DISCHARGE_EFF: float = ROUND_TRIP_EFF ** 0.5

# ---------------------------------------------------------------------------
# Tariff
# ---------------------------------------------------------------------------
TARIFF_OFF_PEAK: float = 0.12    # $/kWh
TARIFF_ON_PEAK: float = 0.28     # $/kWh
DEMAND_CHARGE: float = 10.00     # $/kW (monthly peak demand)


def is_on_peak(hour_utc: int, weekday: int) -> bool:
    """Return True if the UTC hour falls in the ET on-peak window (Mon–Fri 16–21 h ET).

    Simple approximation: UTC−4 (EDT) for the demo period.
    """
    hour_et = (hour_utc - 4) % 24
    return (weekday < 5) and (16 <= hour_et < 21)


def energy_rate(hour_utc: int, weekday: int) -> float:
    """Return the applicable energy rate ($/kWh)."""
    return TARIFF_ON_PEAK if is_on_peak(hour_utc, weekday) else TARIFF_OFF_PEAK


# ---------------------------------------------------------------------------
# SOC simulation
# ---------------------------------------------------------------------------

def step_soc(
    soc_kwh: float,
    action_kw: float,
    dt_h: float = 1.0,
    capacity_kwh: float = CAPACITY_KWH,
    max_power_kw: float = MAX_POWER_KW,
) -> tuple[float, float]:
    """Advance SOC by one timestep.

    Parameters
    ----------
    soc_kwh : current state of charge (kWh)
    action_kw : commanded battery power (+ = charge, − = discharge)
    dt_h : timestep length in hours

    Returns
    -------
    new_soc_kwh : clipped to [SOC_MIN_KWH, capacity_kwh]
    actual_kw   : realised power after clipping
    """
    # Clip action to power limits
    action_kw = float(np.clip(action_kw, -max_power_kw, max_power_kw))

    if action_kw >= 0:
        energy_in = action_kw * CHARGE_EFF * dt_h
        new_soc = min(soc_kwh + energy_in, capacity_kwh)
        actual_energy = new_soc - soc_kwh
        actual_kw = actual_energy / (CHARGE_EFF * dt_h) if dt_h > 0 else 0.0
    else:
        energy_out = abs(action_kw) / DISCHARGE_EFF * dt_h
        new_soc = max(soc_kwh - energy_out, SOC_MIN_KWH)
        actual_energy = soc_kwh - new_soc
        actual_kw = -(actual_energy * DISCHARGE_EFF / dt_h) if dt_h > 0 else 0.0

    return float(new_soc), float(actual_kw)


def simulate_battery(
    actions_kw: np.ndarray,
    soc0_kwh: float = CAPACITY_KWH / 2,
    dt_h: float = 1.0,
) -> np.ndarray:
    """Simulate a full sequence of battery actions.

    Returns
    -------
    soc_kwh : shape (len(actions)+1,) — SOC trajectory including initial value.
    """
    soc = soc0_kwh
    trajectory = [soc]
    for a in actions_kw:
        soc, _ = step_soc(soc, float(a), dt_h)
        trajectory.append(soc)
    return np.array(trajectory)


# ---------------------------------------------------------------------------
# Bill calculation
# ---------------------------------------------------------------------------

def compute_bill(
    grid_import_kw: np.ndarray,
    hours_utc: np.ndarray,
    weekdays: np.ndarray,
    dt_h: float = 1.0,
) -> dict[str, float]:
    """Compute the monthly electricity bill for a sequence of hourly imports.

    Parameters
    ----------
    grid_import_kw : hourly net import from grid (kW); exports treated as zero.
    hours_utc      : UTC hour-of-day for each timestep.
    weekdays       : day-of-week (0=Mon … 6=Sun) for each timestep.

    Returns
    -------
    dict with keys: energy_cost, demand_cost, total_cost (all in $).
    """
    import_kw = np.maximum(grid_import_kw, 0.0)

    rates = np.array([
        energy_rate(int(h), int(w)) for h, w in zip(hours_utc, weekdays)
    ])
    energy_cost = float(np.sum(import_kw * rates * dt_h))
    demand_cost = float(np.max(import_kw) * DEMAND_CHARGE)

    return {
        "energy_cost": energy_cost,
        "demand_cost": demand_cost,
        "total_cost": energy_cost + demand_cost,
    }
