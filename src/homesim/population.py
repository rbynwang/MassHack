"""Population sampler: one row of parameters per home (guideline sections 2, 3, 8)."""

from __future__ import annotations

import numpy as np
import pandas as pd

HEATING_CODES = {"heat_pump": "hp", "gas_central_ac": "gasca", "gas_window_ac": "gaswa"}


def _choice(rng: np.random.Generator, shares: dict, n: int) -> np.ndarray:
    keys = list(shares.keys())
    p = np.array([float(shares[k]) for k in keys])
    return rng.choice(keys, size=n, p=p / p.sum())


def _u(rng: np.random.Generator, bounds, n: int) -> np.ndarray:
    lo, hi = bounds
    return rng.uniform(lo, hi, size=n)


def sample_homes(cfg: dict, n_homes: int, mode: str, rng: np.random.Generator) -> pd.DataFrame:
    if mode not in ("representative", "balanced"):
        raise ValueError(f"mode must be representative or balanced, got {mode!r}")
    pop = cfg["population"][mode]
    hc = cfg["home"]
    tc = cfg["thermostat"]
    n = n_homes

    heating_combo = _choice(rng, pop["heating"], n)
    is_hp = heating_combo == "heat_pump"
    heating_type = np.where(is_hp, "heat_pump", "gas_furnace")
    cooling_type = np.select(
        [is_hp, heating_combo == "gas_central_ac"], ["heat_pump", "central_ac"], "window_ac"
    )

    has_pv = rng.random(n) < pop["p_solar"]
    p_bat = np.where(has_pv, pop["p_battery_given_solar"], pop["p_battery_given_no_solar"])
    has_bat = rng.random(n) < p_bat
    n_ev = _choice(rng, pop["ev"], n).astype(int)
    archetype = _choice(rng, pop["archetype"], n)

    # Floor area: lognormal around the median, clipped to the stated range.
    s = hc["sqft"]
    sqft = np.exp(rng.normal(np.log(s["median"]), s["sigma"], n)).clip(s["min"], s["max"])
    vintage = _choice(rng, hc["vintage_shares"], n)

    ua_med = np.empty(n)
    tau = np.empty(n)
    for v in hc["vintage_shares"]:
        m = vintage == v
        ua_med[m] = _u(rng, hc["ua_kw_per_c_at_median_sqft"][v], m.sum())
        tau[m] = _u(rng, hc["tau_h"][v], m.sum())
    area_ratio = sqft / s["median"]
    ua = ua_med * area_ratio ** hc["ua_area_exponent"]
    capacitance = tau * ua

    spread = hc["hp_capacity_spread"]
    hp_cap = ua * hc["hp_capacity_design_delta_c"] * rng.uniform(1 - spread, 1 + spread, n)
    cool_cap = np.select(
        [cooling_type == "heat_pump", cooling_type == "central_ac"],
        [hp_cap, ua * hc["central_ac_capacity_kw_per_ua"]],
        hc["window_ac_max_kw_thermal"],
    )

    pv_kw_dc = np.where(has_pv, _u(rng, hc["pv_kw_dc"], n), 0.0)
    pv_derate = np.where(has_pv, _u(rng, hc["pv_derate"], n), np.nan)
    pv_noise = np.where(has_pv, rng.uniform(-hc["pv_noise_max_frac"], hc["pv_noise_max_frac"], n), 0.0)

    bat_kwh = np.where(has_bat, _u(rng, hc["battery_kwh"], n), 0.0)
    bat_kw = np.where(has_bat, _u(rng, hc["battery_kw"], n), 0.0)
    bat_eff = np.where(has_bat, _u(rng, hc["battery_eff"], n), np.nan)
    bat_res = np.where(has_bat, _u(rng, hc["battery_reserve_pct"], n), np.nan)

    charger_choice = _choice(rng, cfg["ev"]["charger_kw"], n).astype(float)
    ev_charger_kw = np.where(n_ev > 0, charger_choice, 0.0)

    no_setback = rng.random(n) < tc["p_no_setback"]
    setpoint_winter = _u(rng, tc["winter_setpoint_c"], n)
    setback = np.where(no_setback, np.nan, _u(rng, tc["setback_c"], n))
    setback = np.where(setback >= setpoint_winter, np.nan, setback)
    setpoint_summer = _u(rng, tc["summer_setpoint_c"], n)

    ewh = cfg["appliances"]["electric_water_heater"]["p_has"]
    has_ewh = rng.random(n) < np.where(is_hp, ewh["heat_pump"], ewh["gas"])

    # Home-level split (time split is applied on top, see DATACARD.md).
    fr = cfg["splits"]["home_fractions"]
    order = rng.permutation(n)
    n_train = int(round(fr["train"] * n))
    n_val = int(round(fr["val"] * n))
    split = np.empty(n, dtype=object)
    split[order[:n_train]] = "train"
    split[order[n_train:n_train + n_val]] = "val"
    split[order[n_train + n_val:]] = "test"

    home_type = [
        f"{HEATING_CODES[h]}_{'pv' if p else 'nopv'}_{'bat' if b else 'nobat'}_ev{e}"
        for h, p, b, e in zip(heating_combo, has_pv, has_bat, n_ev)
    ]

    homes = pd.DataFrame(
        {
            "home_id": [f"H{i:05d}" for i in range(n)],
            "home_type": home_type,
            "archetype": archetype,
            "sqft": sqft.round(0),
            "vintage": vintage,
            "ua_kw_per_c": ua,
            "tau_h": tau,
            "capacitance_kwh_per_c": capacitance,
            "hp_capacity_kw": np.where(is_hp, hp_cap, np.nan),
            "cooling_capacity_kw": cool_cap,
            "heating_type": heating_type,
            "cooling_type": cooling_type,
            "pv_kw_dc": pv_kw_dc,
            "pv_derate": pv_derate,
            "pv_noise_frac": pv_noise,
            "battery_kwh": bat_kwh,
            "battery_kw": bat_kw,
            "battery_eff": bat_eff,
            "battery_reserve_pct": bat_res,
            "n_ev": n_ev,
            "ev_charger_kw": ev_charger_kw,
            "setpoint_winter_c": setpoint_winter,
            "setback_c": setback,
            "setpoint_summer_c": setpoint_summer,
            "comfort_band_c": _u(rng, tc["comfort_band_c"], n),
            "compliance_rate": _u(rng, cfg["compliance_rate"], n),
            "has_electric_water_heater": has_ewh,
            "internal_gain_occupied_kw": _u(rng, hc["internal_gain_occupied_kw"], n),
            "window_aperture_m2": _u(rng, hc["window_aperture_m2_at_median_sqft"], n) * area_ratio,
            "furnace_blower_kw": np.where(is_hp, 0.0, _u(rng, hc["furnace_blower_kw"], n)),
            "window_ac_fraction": np.where(
                cooling_type == "window_ac", _u(rng, hc["window_ac_fraction"], n), np.nan
            ),
            "split": split,
        }
    )
    return homes
