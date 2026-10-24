import numpy as np

from masshack.physics import Battery, Tariff, bill, simulate_schedule
from masshack.optimizer import optimize_battery, vendor_default


def test_energy_balance_and_soc_limits():
    b = Battery(capacity_kwh=20, power_kw=5)
    load = np.full(24, 4.0); pv = np.zeros(24)
    r = simulate_schedule(b, load, pv, np.zeros(24), np.full(24, 10.0), dt=1)
    assert r["discharge_kw"].max() <= 5 + 1e-9
    assert r["soc"].min() >= b.soc_min - 1e-9
    assert np.allclose(load - r["discharge_kw"], r["import_kw"] - r["export_kw"])


def test_demand_charge_on_monthly_max():
    t = Tariff(energy_usd_per_kwh=0.2, demand_usd_per_kw=10, fixed_usd_per_month=0, export_credit_usd_per_kwh=0)
    out = bill(np.array([1, 5, 2.0]), np.zeros(3), t, dt=1, prior_peak_kw=3)
    assert abs(out["demand_usd"] - 20) < 1e-9          # only the 2 kW above the prior peak
    assert abs(out["energy_usd"] - 1.6) < 1e-9


def test_optimizer_shaves_peak_better_than_vendor():
    t = Tariff(energy_usd_per_kwh=0.18, demand_usd_per_kw=15, export_credit_usd_per_kwh=0.05, fixed_usd_per_month=0)
    b = Battery(capacity_kwh=40, power_kw=10)
    h = np.arange(24)
    pv = np.clip(8 * np.sin((h - 6) / 12 * np.pi), 0, None)
    load = 6 + 12 * np.exp(-((h - 16) ** 2) / 6)        # late-afternoon peak after the sun fades
    opt = optimize_battery(load, pv, b, t, dt=1)
    ven = vendor_default(load, pv, b, dt=1)
    assert opt["ok"]
    assert opt["peak_kw"] < ven["import_kw"].max() - 0.5


def test_forced_delta_costs_money():
    t = Tariff(); b = Battery(capacity_kwh=20, power_kw=5)
    load = np.full(24, 5.0); pv = np.zeros(24)
    base = optimize_battery(load, pv, b, t)
    net = base["import_kw"] - base["export_kw"]
    forced = optimize_battery(load, pv, b, t, forced_import_delta={17: -3.0}, base_import=net)
    assert forced["ok"] and forced["objective_usd"] >= base["objective_usd"] - 1e-6
