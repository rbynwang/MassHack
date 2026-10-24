"""Physics: one-node thermal model, heat pump / AC / backup heat, PV (guideline section 4).

The thermostat is an ideal hourly controller: it delivers exactly the heat (or
cooling) needed to end the hour at its setpoint, limited by equipment capacity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from homesim.behavior import Behavior
from homesim.inputs import Inputs


def cop_heat(t_out_c: np.ndarray) -> np.ndarray:
    return np.clip(2.8 + 0.08 * t_out_c, 1.5, 4.5)


def cop_cool(t_out_c: np.ndarray) -> np.ndarray:
    return np.clip(4.5 - 0.1 * (t_out_c - 25.0), 2.0, 4.5)


@dataclass
class PhysicsResult:
    t_in_c: np.ndarray        # indoor temperature at the start of each hour (N, H)
    heat_pump_kw: np.ndarray  # heat pump electricity, heating + cooling (N, H)
    backup_heat_kw: np.ndarray
    ac_kw: np.ndarray         # central / window AC electricity (gas homes)
    blower_kw: np.ndarray     # gas furnace blower
    pv_kw: np.ndarray
    unmet_heat_kwh_th: np.ndarray  # thermal shortfall (gas homes never short)
    unmet_cool_kwh_th: np.ndarray


def simulate_physics(cfg: dict, homes: pd.DataFrame, inp: Inputs, beh: Behavior) -> PhysicsResult:
    hc = cfg["home"]
    n, H = len(homes), inp.n_hours
    dt = 1.0

    ua = homes["ua_kw_per_c"].to_numpy()
    cap = homes["capacitance_kwh_per_c"].to_numpy()
    is_hp = (homes["heating_type"] == "heat_pump").to_numpy()
    hp_cap = np.nan_to_num(homes["hp_capacity_kw"].to_numpy())
    cool_cap = homes["cooling_capacity_kw"].to_numpy()
    is_window = (homes["cooling_type"] == "window_ac").to_numpy()
    win_frac = np.nan_to_num(homes["window_ac_fraction"].to_numpy(), nan=1.0)
    blower = homes["furnace_blower_kw"].to_numpy()
    furnace_cap = ua * hc["furnace_capacity_kw_per_ua"]
    aperture = homes["window_aperture_m2"].to_numpy()
    backup_cap = float(hc["backup_heat_max_kw"])

    t_out = inp.temp_out_c
    q_solar = (inp.solar_w_m2 / 1000.0)[None, :] * aperture[:, None]
    copH = cop_heat(t_out)
    copC = cop_cool(t_out)

    t_in = np.empty((n, H))
    hp_kw = np.zeros((n, H))
    backup_kw = np.zeros((n, H))
    ac_kw = np.zeros((n, H))
    blower_kw = np.zeros((n, H))
    unmet_h = np.zeros((n, H))
    unmet_c = np.zeros((n, H))

    T = 0.5 * (homes["setpoint_winter_c"].to_numpy() + homes["setpoint_summer_c"].to_numpy())
    for t in range(H):
        t_in[:, t] = T
        gains = ua * (t_out[t] - T) + beh.internal_gain_kw[:, t] + q_solar[:, t]
        t_free = T + dt / cap * gains

        need_h = np.maximum(0.0, cap / dt * (beh.heat_setpoint_c[:, t] - t_free))
        sp_c = beh.cool_setpoint_c[:, t]
        need_c = np.where(np.isfinite(sp_c), np.maximum(0.0, cap / dt * (t_free - np.where(np.isfinite(sp_c), sp_c, 0.0))), 0.0)

        # Heating
        q_hp_heat = np.where(is_hp, np.minimum(need_h, hp_cap), 0.0)
        q_backup = np.where(is_hp, np.minimum(need_h - q_hp_heat, backup_cap), 0.0)
        unmet_h[:, t] = np.where(is_hp, need_h - q_hp_heat - q_backup, 0.0)
        q_gas = np.where(is_hp, 0.0, need_h)
        # Cooling
        target_c = np.where(is_window, win_frac * need_c, need_c)
        q_cool = np.minimum(target_c, cool_cap)
        unmet_c[:, t] = need_c - q_cool

        hp_kw[:, t] = q_hp_heat / copH[t] + np.where(is_hp, q_cool / copC[t], 0.0)
        backup_kw[:, t] = q_backup / hc["backup_heat_cop"]
        ac_kw[:, t] = np.where(is_hp, 0.0, q_cool / copC[t])
        blower_kw[:, t] = np.where(is_hp, 0.0, blower * np.minimum(1.0, q_gas / furnace_cap))

        T = t_free + dt / cap * (q_hp_heat + q_backup + q_gas - q_cool)

    pv_scale = (
        homes["pv_kw_dc"].to_numpy()
        * np.nan_to_num(homes["pv_derate"].to_numpy())
        / cfg["inputs"]["pv_reference_derate"]
        * (1.0 + homes["pv_noise_frac"].to_numpy())
    )
    pv_kw = pv_scale[:, None] * inp.pv_per_kw_dc[None, :]

    return PhysicsResult(
        t_in_c=t_in,
        heat_pump_kw=hp_kw,
        backup_heat_kw=backup_kw,
        ac_kw=ac_kw,
        blower_kw=blower_kw,
        pv_kw=pv_kw,
        unmet_heat_kwh_th=unmet_h,
        unmet_cool_kwh_th=unmet_c,
    )
