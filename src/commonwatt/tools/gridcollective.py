"""GridCollectiveTool: the team's trained model, called by the agents as their tool.

What the agents get from it, per member that exists in the trained model (`Twin.model_id`):
- forecast: the trained, calibrated LightGBM P10/P50/P90 load forecast for June 24, 2025 (from the model's own
  forecast cache, `data/gridcollective/forecast_cache.pkl`, written by `run_all.py` on branch model/gridcollective).
- decide: for members with a battery, the GridCollective battery planner (HiGHS linear program with the G-2
  demand charge) runs on that forecast twice, without and with the coordinator's requested import cut in the
  window. The extra cost is the member's price for the request; the largest cut the planner can hold is what
  the agent can accept. The agent declines when the posted price is below that cost.

Members the trained model does not know (our homesim homes, the school, library_01) use the labeled stand-in
(`MockModelTool`). Every call is recorded in `self.calls` and exported to the demo.
"""

from __future__ import annotations

import pickle

import numpy as np

from commonwatt.members import EVENT_DAY, SOC_DEFAULT_GRID, SOC_DEFAULT_PV, SOC_MAX
from commonwatt.tools.contract import Decision, Flexibility, Forecast, MemberContext
from commonwatt.tools.mock import MockModelTool, _floor2
from gridcollective import CACHE, SOURCE_COMMIT
from gridcollective.optimizer import optimize_battery
from gridcollective.physics import Battery, Tariff


class GridCollectiveTool(MockModelTool):
    def __init__(self) -> None:
        with open(CACHE, "rb") as fh:
            c = pickle.load(fh)
        self.model_name = c["used"]
        self.fc = {k[0]: v for k, v in c["fc"].items()
                   if str(k[1])[:10] == EVENT_DAY and k[2] == "baseline" and float(k[3]) == 0.0}
        self.tariff = Tariff()                         # Town of Concord MA G-2, as in the trained model
        self.calls: list[dict] = []
        self.trained_members: set[str] = set()
        self.name = f"GridCollective trained model ({SOURCE_COMMIT}): LightGBM forecasts + battery LP"

    # ------------------------------------------------------------ helpers
    def _mid(self, ctx: MemberContext) -> str | None:
        mid = getattr(ctx.twin, "model_id", None)
        return mid if mid in self.fc else None

    def _quantiles(self, mid: str):
        f = self.fc[mid]
        return (f["p10"].to_numpy()[:24].astype(float), f["p50"].to_numpy()[:24].astype(float),
                f["p90"].to_numpy()[:24].astype(float))

    def _log(self, ctx, method, summary, trained=True):
        self.calls.append({"member": ctx.member_id, "model_id": getattr(ctx.twin, "model_id", None),
                           "method": method, "source": "trained model" if trained else "stand-in", "summary": summary})

    def _battery(self, tw) -> Battery:
        b = tw.battery
        s0 = SOC_DEFAULT_PV if tw.pv_kw.max() > 0.5 else SOC_DEFAULT_GRID
        eta = b["eff_rt"] ** 0.5
        return Battery(capacity_kwh=b["kwh"], power_kw=b["kw"], eta_charge=eta, eta_discharge=eta,
                       soc_min=b["reserve_pct"] / 100, soc_max=SOC_MAX, soc0=s0)

    # ------------------------------------------------------------ member side
    def forecast(self, ctx: MemberContext, horizon_h: int = 24) -> Forecast:
        mid = self._mid(ctx)
        if mid is None:
            fc = super().forecast(ctx, horizon_h)
            self._log(ctx, "forecast", "stand-in: the building's own simulated day", trained=False)
            return fc
        self.trained_members.add(ctx.member_id)
        p10, p50, p90 = self._quantiles(mid)
        pv = ctx.twin.pv_kw
        self._log(ctx, "forecast", f"LightGBM P50 peak {p50.max():.1f} kW at {int(p50.argmax())}:00, "
                                   f"band {p10.max():.1f}-{p90.max():.1f} kW")
        return Forecast(hours=list(range(horizon_h)), load_kw=p50.round(3).tolist(), pv_kw=pv.round(3).tolist(),
                        net_kw=(p50 - pv).round(3).tolist(), net_p10_kw=(p10 - pv).round(3).tolist(),
                        net_p90_kw=(p90 - pv).round(3).tolist(), method=self.model_name)

    def _price_request(self, ctx: MemberContext, kw: float, window: list[int]):
        """Battery planner on the trained forecast: base plan vs plan holding `kw` less in every window hour."""
        mid, tw = self._mid(ctx), ctx.twin
        _, p50, p90 = self._quantiles(mid)
        load = np.maximum(p50, 0.9 * p90)               # protect the peak, as the trained agents do
        bat = self._battery(tw)
        base = optimize_battery(load, tw.pv_kw, bat, self.tariff)
        if not base.get("ok"):
            return None, None
        net = base["import_kw"] - base["export_kw"]
        forced = optimize_battery(load, tw.pv_kw, bat, self.tariff, forced_import_delta={h: -kw for h in window},
                                  base_import=net)
        return base, forced

    def flexibility(self, ctx: MemberContext, window: list[int]) -> Flexibility:
        fl = super().flexibility(ctx, window)
        mid, tw = self._mid(ctx), ctx.twin
        if mid is None or not tw.battery:
            return fl
        # price a typical request: a quarter of what the battery could hold, then smaller until the planner can
        k = max(0.1, 0.25 * min(tw.battery["kw"], fl.sustain_reduce_kw))
        for _ in range(4):
            base, forced = self._price_request(ctx, k, window)
            if base and forced and forced.get("ok"):
                fl.cost_per_kwh = round(max(0.0, forced["objective_usd"] - base["objective_usd"]) / (k * len(window)), 3)
                fl.method = "GridCollective battery LP on the trained forecast"
                break
            k *= 0.5
        self._log(ctx, "flexibility", f"can hold {fl.sustain_reduce_kw:.1f} kW for {len(window)} h, "
                                      f"cost ${fl.cost_per_kwh:.3f}/kWh (battery LP)")
        return fl

    def decide(self, ctx: MemberContext, reduce_kw: float, window: list[int], price: float) -> Decision:
        mid, tw = self._mid(ctx), ctx.twin
        if mid is None or not tw.battery:
            d = super().decide(ctx, reduce_kw, window, price)
            self._log(ctx, "decide", f"{d.decision} {d.kw:.2f} kW (HVAC rule; no battery to plan)", trained=False)
            return d
        # largest cut the battery planner can hold for the whole window (plus the twin's HVAC part), capped by
        # what the building can physically carry out
        physical = tw.plan(reduce_kw, window)
        thermal = physical.thermal_kw
        lo, hi = 0.0, min(reduce_kw, tw.battery["kw"])
        base, forced = self._price_request(ctx, hi, window)
        if not (forced and forced.get("ok")):
            for _ in range(14):
                mid_kw = 0.5 * (lo + hi)
                _, f = self._price_request(ctx, mid_kw, window)
                lo, hi = (mid_kw, hi) if f and f.get("ok") else (lo, mid_kw)
            battery_kw = lo
            base, forced = self._price_request(ctx, battery_kw, window) if battery_kw > 0 else (base, None)
        else:
            battery_kw = hi
        can = min(battery_kw + thermal, physical.kw if physical.kw > 0 else battery_kw + thermal)
        extra = (forced["objective_usd"] - base["objective_usd"]) if (base and forced and forced.get("ok")) else 0.0
        cost = max(0.0, extra) / max(1e-6, battery_kw * len(window)) if battery_kw > 0 else tw.cost_per_kwh
        soc_min = float(np.min(forced["soc"])) * 100 if (forced and forced.get("ok")) else None
        p = tw.plan(min(reduce_kw, can), window)
        predicted = {"battery_min_pct": round(soc_min, 1) if soc_min is not None else p.battery_min_pct,
                     "fixed_kw": {int(h): round(float(v), 3) for h, v in enumerate(p.fixed_delta_kw)
                                  if abs(v) > 1e-3 and h not in window},
                     "model": "GridCollective battery LP", "extra_cost_usd": round(extra, 2)}
        args = dict(prep_kwh=round(p.battery_prep_kwh, 3), rebound_kwh=round(p.battery_recovery_kwh, 3),
                    max_recovery_kw=p.battery_max_kw, predicted=predicted)
        why = f"battery planner: ${cost:.2f}/kWh to hold it, incl. recharge and peak charge"
        if price < cost:
            d = Decision("decline", 0.0, f"price ${price:.2f}/kWh is below my planner's cost ${cost:.2f}/kWh")
        elif can >= reduce_kw - 0.01:
            d = Decision("accept", _floor2(min(reduce_kw, can + 0.01)), why, **args)
        elif can >= 0.1:
            d = Decision("counter", _floor2(can), f"I can hold {_floor2(can):.1f} kW for all {len(window)} h ({why})", **args)
        else:
            d = Decision("decline", 0.0, "no battery room left in this window")
        self._log(ctx, "decide", f"asked {reduce_kw:.2f} kW: {d.decision} {d.kw:.2f} kW; planner extra cost "
                                 f"${extra:.2f} (${cost:.3f}/kWh)")
        return d
