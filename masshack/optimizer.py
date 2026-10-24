"""Battery dispatch optimizer: a linear program each member solves for itself.

minimize   sum_t price_t*imp_t*dt - credit_t*exp_t*dt + demand_rate*max(P - P_prior, 0) + wear*(c+d)*dt
subject to load_t - pv_t + c_t - d_t = imp_t - exp_t
           e_{t+1} = e_t + (eta_c c_t - d_t/eta_d) dt,  e_min <= e_t <= e_max
           0 <= c_t, d_t <= power,  P >= imp_t
Optional `forced` lets the coordinator ask: "what does it cost you to change your import at hour h by x kW?"
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

from .physics import Battery, Tariff


def optimize_battery(load_kw, pv_kw, battery: Battery, tariff: Tariff, dt: float = 1.0,
                     price_usd_per_kwh=None, prior_peak_kw: float = 0.0, e0: float | None = None,
                     e_end_min: float | None = None, wear_usd_per_kwh: float = 0.01,
                     forced_import_delta: dict | None = None, base_import=None, import_cap: dict | None = None) -> dict:
    """Solve the member's own plan. Returns schedule, flows and objective (USD).

    forced_import_delta: {t: delta_kw}. Requires base_import; constrains imp_t - exp_t = base_net_t + delta.
    """
    load = np.asarray(load_kw, float)
    pv = np.asarray(pv_kw, float)
    n = len(load)
    price = np.full(n, tariff.energy_usd_per_kwh) if price_usd_per_kwh is None else np.asarray(price_usd_per_kwh, float)
    credit = np.full(n, tariff.export_credit_usd_per_kwh)
    e0 = battery.capacity_kwh * battery.soc0 if e0 is None else e0
    e_end_min = e0 * 0.98 if e_end_min is None else e_end_min  # do not drain the battery for free

    # variable layout: c(n) d(n) imp(n) exp(n) e(n+1) P(1) Pex(1)
    ic, id_, ii, ie, iE = 0, n, 2 * n, 3 * n, 4 * n
    iP, iPx = 5 * n + 1, 5 * n + 2
    nv = 5 * n + 3
    cost = np.zeros(nv)
    cost[ic:ic + n] = wear_usd_per_kwh * dt
    cost[id_:id_ + n] = wear_usd_per_kwh * dt
    cost[ii:ii + n] = price * dt
    cost[ie:ie + n] = -credit * dt
    cost[iPx] = tariff.demand_usd_per_kw

    neq = n + n + 1 + (len(forced_import_delta) if forced_import_delta else 0)
    A_eq = lil_matrix((neq, nv))
    b_eq = np.zeros(neq)
    r = 0
    for t in range(n):  # power balance: c - d - imp + exp = pv - load
        A_eq[r, ic + t] = 1; A_eq[r, id_ + t] = -1; A_eq[r, ii + t] = -1; A_eq[r, ie + t] = 1
        b_eq[r] = pv[t] - load[t]; r += 1
    for t in range(n):  # energy dynamics
        A_eq[r, iE + t + 1] = 1; A_eq[r, iE + t] = -1
        A_eq[r, ic + t] = -battery.eta_charge * dt; A_eq[r, id_ + t] = dt / battery.eta_discharge
        r += 1
    A_eq[r, iE] = 1; b_eq[r] = e0; r += 1
    if forced_import_delta:
        base = np.asarray(base_import, float)
        for t, delta in forced_import_delta.items():
            A_eq[r, ii + t] = 1; A_eq[r, ie + t] = -1; b_eq[r] = base[t] + delta; r += 1

    A_ub = lil_matrix((n + 1, nv))
    b_ub = np.zeros(n + 1)
    for t in range(n):  # imp_t <= P
        A_ub[t, ii + t] = 1; A_ub[t, iP] = -1
    A_ub[n, iP] = 1; A_ub[n, iPx] = -1; b_ub[n] = prior_peak_kw  # Pex >= P - prior

    imp_bounds = [(0, None)] * n
    for t, cap in (import_cap or {}).items():
        if 0 <= t < n:
            imp_bounds[t] = (0, max(float(cap), 0.0))
    bounds = ([(0, battery.power_kw)] * (2 * n) + imp_bounds + [(0, None)] * n
              + [(battery.e_min, battery.e_max)] * n + [(min(max(e_end_min, battery.e_min), battery.e_max), battery.e_max)]
              + [(0, None), (0, None)])
    res = linprog(cost, A_ub=A_ub.tocsr(), b_ub=b_ub, A_eq=A_eq.tocsr(), b_eq=b_eq, bounds=bounds, method="highs")
    if res.status != 0:
        return {"ok": False, "message": res.message}
    x = res.x
    return {
        "ok": True,
        "objective_usd": float(res.fun),
        "charge_kw": x[ic:ic + n], "discharge_kw": x[id_:id_ + n],
        "import_kw": x[ii:ii + n], "export_kw": x[ie:ie + n],
        "soc": x[iE + 1:iE + n + 1] / battery.capacity_kwh,
        "peak_kw": float(x[iP]),
    }


def vendor_default(load_kw, pv_kw, battery: Battery, dt: float = 1.0, e0: float | None = None) -> dict:
    """What most installers ship: store surplus solar, discharge whenever load exceeds solar. Ignores weather and tariff."""
    from .physics import simulate_schedule
    net = np.asarray(load_kw) - np.asarray(pv_kw)
    return simulate_schedule(battery, load_kw, pv_kw, np.clip(-net, 0, None), np.clip(net, 0, None), dt, e0)


def mpc_realize(load_act, pv_act, fc_load, battery: Battery, tariff: Tariff, dt: float = 1.0, price=None,
                import_cap: dict | None = None, decay: float = 0.6):
    """Hourly re-planning (model predictive control) with the ACTUAL load revealed hour by hour.

    At each hour: correct the rest of the forecast by the latest forecast error (fading with `decay`), re-solve the
    battery plan for the remaining hours from the current charge, then execute only this hour's action under the
    actual load. `import_cap` holds hours committed to the collective (import must stay at or below the cap).
    """
    from .physics import simulate_schedule
    n = len(load_act)
    e = battery.capacity_kwh * battery.soc0
    c_r, d_r, soc = np.zeros(n), np.zeros(n), np.zeros(n)
    peak_so_far, err = 0.0, 0.0
    for t in range(n):
        k = np.arange(n - t)
        fc = np.maximum(np.asarray(fc_load[t:], float) + err * decay ** k, 0)
        caps = {h - t: v for h, v in (import_cap or {}).items() if h >= t}
        pr = None if price is None else np.asarray(price)[t:]
        p = optimize_battery(fc, pv_act[t:], battery, tariff, dt=dt, price_usd_per_kwh=pr, prior_peak_kw=peak_so_far,
                             e0=e, e_end_min=min(e, battery.capacity_kwh * battery.soc0), import_cap=caps)
        if not p.get("ok") and caps:
            p = optimize_battery(fc, pv_act[t:], battery, tariff, dt=dt, price_usd_per_kwh=pr, prior_peak_kw=peak_so_far,
                                 e0=e, e_end_min=battery.e_min)
        c, d = (float(p["charge_kw"][0]), float(p["discharge_kw"][0])) if p.get("ok") else (0.0, 0.0)
        step = simulate_schedule(battery, load_act[t:t + 1], pv_act[t:t + 1], [c], [d], dt, e0=e)
        e = step["e_end"]; c_r[t], d_r[t], soc[t] = step["charge_kw"][0], step["discharge_kw"][0], step["soc"][0]
        peak_so_far = max(peak_so_far, float(step["import_kw"][0]))
        err = float(load_act[t] - fc_load[t])
    from .physics import settle_flows
    imp, exp = settle_flows(load_act, pv_act, c_r, d_r)
    return {"charge_kw": c_r, "discharge_kw": d_r, "soc": soc, "import_kw": imp, "export_kw": exp, "e_end": e}


def optimize_battery_scenarios(loads_kw, weights, pv_kw, battery: Battery, tariff: Tariff, dt: float = 1.0,
                               prior_peak_kw: float = 0.0, e0: float | None = None, e_end_min: float | None = None,
                               wear_usd_per_kwh: float = 0.01, import_cap: dict | None = None, price_usd_per_kwh=None) -> dict:
    """One battery schedule that minimizes the EXPECTED bill over several load scenarios (stochastic LP).

    Charge/discharge are shared; each scenario has its own import/export and its own peak. A demand charge punishes
    under-estimating the peak much more than over-estimating it, so planning against the spread of outcomes (not one
    forecast line) keeps energy in reserve for the hour that might be the peak.
    """
    L = np.atleast_2d(np.asarray(loads_kw, float)); S, n = L.shape
    w = np.asarray(weights, float); w = w / w.sum()
    pv = np.asarray(pv_kw, float)
    e0 = battery.capacity_kwh * battery.soc0 if e0 is None else e0
    e_end_min = e0 * 0.98 if e_end_min is None else e_end_min
    # layout: c(n) d(n) e(n+1) | per scenario: imp(n) exp(n) P Pex
    ic, id_, iE = 0, n, 2 * n
    base = 3 * n + 1; blk = 2 * n + 2
    nv = base + S * blk
    cost = np.zeros(nv)
    cost[ic:ic + 2 * n] = wear_usd_per_kwh * dt
    neq = S * n + n + 1
    A_eq = lil_matrix((neq, nv)); b_eq = np.zeros(neq); r = 0
    A_ub = lil_matrix((S * (n + 1), nv)); b_ub = np.zeros(S * (n + 1)); u = 0
    bounds = [(0, battery.power_kw)] * (2 * n) + [(battery.e_min, battery.e_max)] * n + \
             [(min(max(e_end_min, battery.e_min), battery.e_max), battery.e_max)]
    for s in range(S):
        o = base + s * blk; ii, ie, iP, iPx = o, o + n, o + 2 * n, o + 2 * n + 1
        cost[ii:ii + n] = w[s] * (tariff.energy_usd_per_kwh if price_usd_per_kwh is None else np.asarray(price_usd_per_kwh, float)) * dt
        cost[ie:ie + n] = -w[s] * tariff.export_credit_usd_per_kwh * dt
        cost[iPx] = w[s] * tariff.demand_usd_per_kw
        for t in range(n):
            A_eq[r, ic + t] = 1; A_eq[r, id_ + t] = -1; A_eq[r, ii + t] = -1; A_eq[r, ie + t] = 1
            b_eq[r] = pv[t] - L[s, t]; r += 1
            A_ub[u, ii + t] = 1; A_ub[u, iP] = -1; u += 1
        A_ub[u, iP] = 1; A_ub[u, iPx] = -1; b_ub[u] = prior_peak_kw; u += 1
        ib = [(0, None)] * n
        for t, cap in (import_cap or {}).items():
            if 0 <= t < n:
                ib[t] = (0, max(float(cap), 0.0))
        bounds += ib + [(0, None)] * n + [(0, None), (0, None)]
    for t in range(n):
        A_eq[r, iE + t + 1] = 1; A_eq[r, iE + t] = -1
        A_eq[r, ic + t] = -battery.eta_charge * dt; A_eq[r, id_ + t] = dt / battery.eta_discharge; r += 1
    A_eq[r, iE] = 1; b_eq[r] = e0
    res = linprog(cost, A_ub=A_ub.tocsr(), b_ub=b_ub, A_eq=A_eq.tocsr(), b_eq=b_eq, bounds=bounds, method="highs")
    if res.status != 0:
        return {"ok": False, "message": res.message}
    x = res.x
    return {"ok": True, "charge_kw": x[ic:ic + n], "discharge_kw": x[id_:id_ + n], "soc": x[iE + 1:iE + n + 1] / battery.capacity_kwh}


def forecast_scenarios(p10, p50, p90, ks=(-1.0, -0.5, 0.0, 0.5, 1.0, 1.5), weights=None):
    """Load scenarios from a quantile forecast: p50 + k * half-width (k=-1 ~ P10, k=+1 ~ P90)."""
    p10, p50, p90 = (np.asarray(v, float) for v in (p10, p50, p90))
    up, dn = np.maximum(p90 - p50, 0), np.maximum(p50 - p10, 0)
    S = np.array([p50 + (k * up if k >= 0 else k * dn) for k in ks])
    if weights is None:
        weights = np.exp(-0.5 * (np.asarray(ks) / 0.78) ** 2)       # 0.78 ~ P90 half-width of a standard normal / 1.645
    return np.maximum(S, 0), np.asarray(weights, float)


def mpc_realize_robust(load_act, pv_act, fc_q: dict, battery: Battery, tariff: Tariff, dt: float = 1.0,
                       decay: float = 0.6, ratio: bool = False, ks=(-1.0, -0.5, 0.0, 0.5, 1.0, 1.5),
                       import_cap: dict | None = None, price=None):
    """Hourly re-planning against forecast SCENARIOS (stochastic MPC) instead of one forecast line."""
    from .physics import simulate_schedule, settle_flows
    n = len(load_act)
    p10, p50, p90 = (np.asarray(fc_q[k], float) for k in ("p10", "p50", "p90"))
    e = battery.capacity_kwh * battery.soc0
    c_r, d_r, soc = np.zeros(n), np.zeros(n), np.zeros(n)
    peak_so_far, err, rat = 0.0, 0.0, 1.0
    for t in range(n):
        k = np.arange(n - t)
        if ratio:
            f = 1 + (rat - 1) * decay ** k
            q = [v[t:] * f for v in (p10, p50, p90)]
        else:
            q = [np.maximum(v[t:] + err * decay ** k, 0) for v in (p10, p50, p90)]
        S, w = forecast_scenarios(*q, ks=ks)
        caps = {h - t: v for h, v in (import_cap or {}).items() if h >= t}
        kw = dict(dt=dt, prior_peak_kw=peak_so_far, e0=e, e_end_min=min(e, battery.capacity_kwh * battery.soc0),
                  price_usd_per_kwh=None if price is None else np.asarray(price)[t:])
        p = optimize_battery_scenarios(S, w, pv_act[t:], battery, tariff, import_cap=caps, **kw)
        if not p.get("ok") and caps:      # a cap that some scenario cannot meet: keep the caps on the median only
            p = optimize_battery_scenarios(S, w, pv_act[t:], battery, tariff, **kw)
        c, d = (float(p["charge_kw"][0]), float(p["discharge_kw"][0])) if p.get("ok") else (0.0, 0.0)
        step = simulate_schedule(battery, load_act[t:t + 1], pv_act[t:t + 1], [c], [d], dt, e0=e)
        e = step["e_end"]; c_r[t], d_r[t], soc[t] = step["charge_kw"][0], step["discharge_kw"][0], step["soc"][0]
        peak_so_far = max(peak_so_far, float(step["import_kw"][0]))
        err = float(load_act[t] - p50[t]); rat = float(load_act[t] / max(p50[t], 1e-6))
    imp, exp = settle_flows(load_act, pv_act, c_r, d_r)
    return {"charge_kw": c_r, "discharge_kw": d_r, "soc": soc, "import_kw": imp, "export_kw": exp, "e_end": e}
