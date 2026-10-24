"""Planners — LP (Path 1) and CEM (Path 2 / stretch).

Path 1 : linear program solved with CVXPY every 15 min over 24 h horizon.
Path 2 : cross-entropy method (CEM) planning inside the world model's imagination.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import cvxpy as cp
    _CVXPY_AVAILABLE = True
except ImportError:
    _CVXPY_AVAILABLE = False

from masshack.battery import (
    CAPACITY_KWH,
    MAX_POWER_KW,
    SOC_MIN_KWH,
    CHARGE_EFF,
    DISCHARGE_EFF,
    energy_rate,
    DEMAND_CHARGE,
)


# ---------------------------------------------------------------------------
# LP planner (Path 1)
# ---------------------------------------------------------------------------

def lp_plan(
    load_forecast_kw: np.ndarray,
    pv_forecast_kw: np.ndarray,
    hours_utc: np.ndarray,
    weekdays: np.ndarray,
    soc0_kwh: float = CAPACITY_KWH / 2,
    dt_h: float = 1.0,
) -> dict[str, np.ndarray]:
    """Solve the 24-h battery dispatch LP.

    Minimises energy cost + demand charge over the horizon.  Demand charge is
    linearised via a lifted peak variable.

    Returns
    -------
    dict with keys:
        actions_kw   : optimal battery power (+ charge, − discharge)
        grid_kw      : resulting grid import (clipped to ≥ 0 for billing)
        soc_kwh      : SOC trajectory (len T+1)
    """
    if not _CVXPY_AVAILABLE:
        raise RuntimeError("cvxpy is not installed.")

    T = len(load_forecast_kw)
    rates = np.array([energy_rate(int(h), int(w)) for h, w in zip(hours_utc, weekdays)])

    # Decision variables
    b_ch = cp.Variable(T, nonneg=True)   # charging power (kW)
    b_dis = cp.Variable(T, nonneg=True)  # discharging power (kW)
    soc = cp.Variable(T + 1)
    peak = cp.Variable(nonneg=True)      # peak import for demand charge

    net_from_grid = load_forecast_kw - pv_forecast_kw + b_ch - b_dis * DISCHARGE_EFF

    constraints = [
        soc[0] == soc0_kwh,
        soc[1:] == soc[:-1] + b_ch * CHARGE_EFF * dt_h - b_dis * dt_h,
        soc >= SOC_MIN_KWH,
        soc <= CAPACITY_KWH,
        b_ch <= MAX_POWER_KW,
        b_dis <= MAX_POWER_KW,
    ]
    # Peak demand constraint
    for t in range(T):
        constraints.append(net_from_grid[t] <= peak)

    cost = (
        cp.sum(cp.multiply(rates * dt_h, cp.pos(net_from_grid)))
        + DEMAND_CHARGE * peak
    )
    prob = cp.Problem(cp.Minimize(cost), constraints)
    prob.solve(solver=cp.CLARABEL, verbose=False)

    if prob.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise RuntimeError(f"LP solve failed: {prob.status}")

    actions_kw = b_ch.value - b_dis.value
    grid_kw = net_from_grid.value

    return {
        "actions_kw": actions_kw,
        "grid_kw": grid_kw,
        "soc_kwh": soc.value,
    }


# ---------------------------------------------------------------------------
# Vendor-default baseline
# ---------------------------------------------------------------------------

def vendor_default_actions(T: int, dt_h: float = 1.0) -> np.ndarray:
    """Simple time-based rule: charge at 8 AM, discharge at 6 PM.

    This approximates the out-of-the-box setting many installers ship.
    """
    actions = np.zeros(T)
    for t in range(T):
        hour_et = t % 24  # assumes UTC offset = 0 for simplicity here
        if hour_et == 8:
            actions[t] = MAX_POWER_KW
        elif hour_et == 18:
            actions[t] = -MAX_POWER_KW
    return actions


# ---------------------------------------------------------------------------
# CEM planner (Path 2 stretch goal)
# ---------------------------------------------------------------------------

@dataclass
class CEMPlanner:
    """Cross-entropy method planner that optimises inside a world model.

    Parameters
    ----------
    world_model : callable (soc, features) -> predicted_cost_per_step
    horizon     : planning horizon in timesteps
    n_samples   : number of candidate plans per iteration
    n_elite     : number of elite plans to keep
    n_iters     : CEM iterations
    """

    world_model: object = None
    horizon: int = 24
    n_samples: int = 256
    n_elite: int = 32
    n_iters: int = 5

    def plan(
        self,
        soc0_kwh: float,
        context: np.ndarray,
    ) -> np.ndarray:
        """Return the best action sequence found by CEM."""
        # Initialise action distribution: Gaussian in [−MAX_POWER_KW, MAX_POWER_KW]
        mu = np.zeros(self.horizon)
        sigma = np.ones(self.horizon) * MAX_POWER_KW / 2

        for _ in range(self.n_iters):
            samples = np.random.randn(self.n_samples, self.horizon) * sigma + mu
            samples = np.clip(samples, -MAX_POWER_KW, MAX_POWER_KW)

            costs = np.array([
                self._rollout_cost(samples[i], soc0_kwh, context)
                for i in range(self.n_samples)
            ])
            elite_idx = np.argsort(costs)[: self.n_elite]
            mu = samples[elite_idx].mean(axis=0)
            sigma = samples[elite_idx].std(axis=0) + 1e-6

        return mu

    def _rollout_cost(
        self,
        actions: np.ndarray,
        soc0: float,
        context: np.ndarray,
    ) -> float:
        """Roll out actions in imagination and return total cost."""
        if self.world_model is None:
            return float("inf")
        return self.world_model.imagine_cost(actions, soc0, context)
