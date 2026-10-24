"""Occupant behaviour: occupancy, thermostat schedule, appliance load and EV charging.

All schedules are built per home and local calendar day (shape: homes x days),
then spread onto hours by overlapping each event with the hour interval
[local_hour, local_hour + 1). Events that run past midnight carry into the next
day's early hours.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from homesim.inputs import Inputs


@dataclass
class Behavior:
    occupied: np.ndarray          # bool (N, H): someone home for most of the hour
    occ_frac: np.ndarray          # float (N, H)
    heat_setpoint_c: np.ndarray   # (N, H)
    cool_setpoint_c: np.ndarray   # (N, H), +inf when cooling is unavailable
    internal_gain_kw: np.ndarray  # (N, H)
    base_kw: np.ndarray           # all non-HVAC, non-EV household load (N, H)
    ev_kw: np.ndarray             # uncontrolled EV charging (N, H)
    vacation_day: np.ndarray      # bool (N, D)


def _overlap(hl: np.ndarray, start: np.ndarray, end: np.ndarray) -> np.ndarray:
    """Fraction of the hour [hl, hl+1) covered by [start, end)."""
    return np.clip(np.minimum(hl + 1.0, end) - np.maximum(hl, start), 0.0, 1.0)


def _spread_event(inp: Inputs, start_d: np.ndarray, dur_d: np.ndarray, active_d: np.ndarray) -> np.ndarray:
    """Spread per-day events (N, D) onto hours (N, H) as fraction-of-hour active.

    Includes the previous day's event shifted by -24 h so events crossing
    midnight are not lost.
    """
    hl = inp.local_hour[None, :]
    di = inp.day_index
    s = np.where(active_d, start_d, np.nan)
    e = s + dur_d
    same = _overlap(hl, s[:, di], e[:, di])
    prev_idx = np.maximum(di - 1, 0)
    ps, pe = s[:, prev_idx] - 24.0, e[:, prev_idx] - 24.0
    prev = np.where(di[None, :] > 0, _overlap(hl, ps, pe), 0.0)
    return np.nan_to_num(same) + np.nan_to_num(prev)


def _vacation_days(rng: np.random.Generator, n: int, n_days: int, weeks_range) -> np.ndarray:
    vac = np.zeros((n, n_days), dtype=bool)
    lo, hi = weeks_range
    n_weeks = rng.integers(lo, hi + 1, size=n)
    for i in range(n):
        starts = rng.choice(np.arange(0, n_days - 7, 7), size=n_weeks[i], replace=False)
        starts = starts + rng.integers(0, 7, size=n_weeks[i])
        for s0 in starts:
            vac[i, s0:min(s0 + 7, n_days)] = True
    return vac


def simulate_behavior(cfg: dict, homes: pd.DataFrame, inp: Inputs, rng: np.random.Generator) -> Behavior:
    n, n_days = len(homes), inp.n_days
    oc = cfg["occupancy"]
    ac = cfg["appliances"]
    tc = cfg["thermostat"]
    hc = cfg["home"]
    workday = np.broadcast_to(inp.day_is_workday[None, :], (n, n_days))

    # --- Occupancy schedule per home-day (local clock hours) -------------------
    def arche(field: str) -> np.ndarray:
        vals = np.array(
            [np.nan if oc["archetypes"][a][field] is None else oc["archetypes"][a][field]
             for a in homes["archetype"]],
            dtype=float,
        )
        return vals[:, None]

    jh = oc["jitter_per_home_h"]
    jd = oc["jitter_per_day_h"]
    home_shift = rng.normal(0, jh, (n, 1))

    def daily(base: np.ndarray) -> np.ndarray:
        return base + home_shift + rng.normal(0, jd, (n, n_days))

    wake = daily(arche("wake")) + np.where(workday, 0.0, oc["weekend_wake_delay_h"])
    sleep = np.minimum(daily(arche("sleep")), 23.95)
    leave = np.where(workday, daily(arche("leave")), np.nan)
    ret = np.where(workday, daily(arche("return")), np.nan)
    dinner = np.where(workday, daily(arche("dinner")), oc["weekend_dinner"] + rng.normal(0, jd, (n, n_days)))

    vacation = _vacation_days(rng, n, n_days, oc["vacation_weeks"])

    hl = inp.local_hour[None, :]
    di = inp.day_index
    vac_h = vacation[:, di]

    awake = _overlap(hl, wake[:, di], sleep[:, di])
    away = np.nan_to_num(_overlap(hl, leave[:, di], ret[:, di]))
    home_awake = np.clip(awake - away, 0.0, 1.0)
    occ_frac = np.where(vac_h, 0.0, 1.0 - away)
    home_awake = np.where(vac_h, 0.0, home_awake)
    occupied = occ_frac >= 0.5

    # --- Thermostat --------------------------------------------------------------
    sp_w = homes["setpoint_winter_c"].to_numpy()[:, None]
    sb = homes["setback_c"].to_numpy()[:, None]
    # Setback from bedtime; recovery ramps linearly over `ramp` hours ending at wake-up
    # (smart-recovery thermostats), instead of a single-hour jump.
    ramp = tc["setback_recovery_ramp_h"]
    recovered = np.clip(1.0 + (hl + 1.0 - wake[:, di]) / ramp, 0.0, 1.0)
    after_bed = _overlap(hl, sleep[:, di], 24.0)
    comfort = recovered * (1.0 - after_bed)
    heat_sp = np.where(np.isnan(sb), sp_w, np.nan_to_num(sb) + (sp_w - np.nan_to_num(sb)) * comfort)
    heat_sp = np.where(vac_h, np.minimum(heat_sp, tc["vacation_heat_setpoint_c"]), heat_sp)

    sp_s = homes["setpoint_summer_c"].to_numpy()[:, None]
    cool_sp = np.broadcast_to(sp_s, (n, inp.n_hours)).copy()
    is_window = (homes["cooling_type"] == "window_ac").to_numpy()[:, None]
    local_md = inp.frame["timestamp_local"].dt.strftime("%m-%d").to_numpy()
    s0, s1 = hc["window_ac_season"]
    in_season = ((local_md >= s0) & (local_md <= s1))[None, :]
    window_ok = occupied & in_season
    cool_sp = np.where(is_window & ~window_ok, np.inf, cool_sp)
    cool_sp = np.where(vac_h, np.inf, cool_sp)

    # --- Internal gains ----------------------------------------------------------
    g_occ = homes["internal_gain_occupied_kw"].to_numpy()[:, None]
    internal = occ_frac * g_occ + (1.0 - occ_frac) * hc["internal_gain_unoccupied_kw"]

    # --- Non-HVAC appliance load -------------------------------------------------
    def per_home(bounds) -> np.ndarray:
        return rng.uniform(bounds[0], bounds[1], (n, 1))

    base_always = per_home(ac["base_kw"])
    plug = per_home(ac["plug_activity_kw"])
    light = per_home(ac["lighting_kw"])
    darkness = np.clip(1.0 - inp.solar_w_m2 / ac["darkness_irradiance_w_m2"], 0.0, 1.0)[None, :]

    is_family = (homes["archetype"] == "family").to_numpy()[:, None]
    rush = np.nan_to_num(_overlap(hl, wake[:, di], leave[:, di]))
    rush_mult = 1.0 + np.where(is_family, oc["family_morning_rush_multiplier"] - 1.0, 0.0) * rush
    activity = home_awake * (plug + light * darkness) * rush_mult

    load = base_always + activity
    active_day = ~vacation

    # Home window for daytime chores: after return on workdays with a commute.
    chore_start = np.where(np.isnan(ret), wake + 1.0, ret + 0.5)

    # Clothes dryer
    d = ac["dryer"]
    p_day = rng.uniform(d["per_week"][0], d["per_week"][1], (n, 1)) / 7.0
    dur = rng.uniform(*d["duration_h"], (n, n_days))
    latest = np.maximum(sleep - dur - 0.5, chore_start + 0.1)
    start = chore_start + rng.random((n, n_days)) * (latest - chore_start)
    on = active_day & (rng.random((n, n_days)) < p_day)
    load = load + d["kw"] * _spread_event(inp, start, dur, on)

    # Oven / range: mostly dinner, some lunches when home at noon.
    o = ac["oven"]
    p_dinner = rng.uniform(*o["p_dinner"], (n, 1))
    dur = rng.uniform(*o["duration_h"], (n, n_days))
    on = active_day & (rng.random((n, n_days)) < p_dinner)
    load = load + o["kw"] * _spread_event(inp, dinner - dur, dur, on)
    home_at_noon = np.isnan(leave)
    dur = rng.uniform(*o["duration_h"], (n, n_days))
    on = active_day & home_at_noon & (rng.random((n, n_days)) < o["p_lunch_if_home"])
    load = load + o["kw"] * _spread_event(inp, 12.0 - dur + rng.normal(0, 0.25, (n, n_days)), dur, on)

    # Dishwasher: after dinner.
    w = ac["dishwasher"]
    p_day = rng.uniform(w["per_week"][0], w["per_week"][1], (n, 1)) / 7.0
    dur = rng.uniform(*w["duration_h"], (n, n_days))
    start = dinner + 1.0 + rng.uniform(0.0, 1.5, (n, n_days))
    on = active_day & (rng.random((n, n_days)) < p_day)
    load = load + w["kw"] * _spread_event(inp, start, dur, on)

    # Electric water heater (if present): morning and evening draws.
    e = ac["electric_water_heater"]
    has_ewh = homes["has_electric_water_heater"].to_numpy()[:, None]
    on = active_day & has_ewh
    dur = rng.uniform(*e["morning_runtime_h"], (n, n_days))
    load = load + e["kw"] * _spread_event(inp, wake + rng.uniform(0, 0.5, (n, n_days)), dur, on)
    dur = rng.uniform(*e["evening_runtime_h"], (n, n_days))
    load = load + e["kw"] * _spread_event(inp, dinner + rng.uniform(0, 1.0, (n, n_days)), dur, on)

    # --- EV: uncontrolled charging at full power from arrival until full ---------
    ev = cfg["ev"]
    n_ev = homes["n_ev"].to_numpy()
    charger = homes["ev_charger_kw"].to_numpy()[:, None]
    ev_kw = np.zeros((n, inp.n_hours))
    next_free = None
    for k in range(int(n_ev.max(initial=0))):
        has_k = (n_ev > k)[:, None]
        mean_kwh = rng.uniform(*ev["mean_daily_kwh"], (n, 1))
        need = np.clip(rng.normal(mean_kwh, ev["daily_cv"] * mean_kwh, (n, n_days)), *ev["daily_kwh_clip"])
        grid_kwh = need / ev["charge_eff"]
        arr_wd = rng.normal(ev["weekday_arrival"]["mean"], ev["weekday_arrival"]["sd"], (n, n_days))
        arr_we = rng.uniform(*ev["weekend_arrival_uniform"], (n, n_days))
        arrival = np.where(workday, arr_wd, arr_we)
        start = arrival if next_free is None else np.maximum(arrival, next_free)
        dur = np.where(charger > 0, grid_kwh / np.where(charger > 0, charger, 1.0), 0.0)
        on = active_day & has_k
        ev_kw = ev_kw + charger * _spread_event(inp, start, dur, on)
        next_free = np.where(on, start + dur, arrival)

    base_kw = np.where(vacation[:, di], base_always, load)

    return Behavior(
        occupied=occupied,
        occ_frac=occ_frac,
        heat_setpoint_c=heat_sp,
        cool_setpoint_c=cool_sp,
        internal_gain_kw=internal,
        base_kw=base_kw,
        ev_kw=ev_kw,
        vacation_day=vacation,
    )
