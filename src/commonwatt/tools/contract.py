"""The interface between the agents and the trained ML model.

Member agents call `forecast`, `flexibility` and `decide` inside their own process, with their own data only.
The coordinator calls `plan_dispatch` with offers only (it never sees meter data or private limits).

To plug in the trained model, write a class with these four methods and run with
    COMMONWATT_TOOL=yourpackage.module:YourModelTool uv run commonwatt-demo
Anything not ready yet can be inherited from `commonwatt.tools.mock.MockModelTool`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import pandas as pd


@dataclass
class MemberContext:
    """Everything a member agent knows about itself. Private: never leaves the member agent."""
    member_id: str
    kind: str                         # large_building | household | small_business | public_institution
    as_of_local: str                  # "2025-06-24 10:00" (America/New_York)
    history: pd.DataFrame             # past hourly meter readings, local index: load_kw, pv_kw, net_kw, temp_out_c
    weather_today: pd.DataFrame       # 24 rows for the event day: temp_out_c, solar_w_m2 (measured, used as forecast)
    assets: dict[str, Any]            # battery {kwh, kw, eff_rt, reserve_pct, soc_pct_at_window}, hvac {...}
    twin: Any = None                  # the mock's digital twin of the member (a trained model may ignore it)


@dataclass
class Forecast:
    hours: list[int]
    load_kw: list[float]
    pv_kw: list[float]
    net_kw: list[float]               # load - pv (+ import, - export)
    net_p10_kw: list[float]
    net_p90_kw: list[float]
    method: str


@dataclass
class Flexibility:
    window: list[int]
    can_reduce_kw: dict[int, float]   # per hour, if asked for that hour alone
    can_increase_kw: dict[int, float]
    sustain_reduce_kw: float          # kW it can hold for every hour of the window
    prep_kwh_per_kwh: float           # energy needed before the window per kWh reduced (pre-cool, pre-charge)
    rebound_kwh_per_kwh: float        # extra energy after the window per kWh reduced (recharge, rebound)
    max_recovery_kw: float
    cost_per_kwh: float
    method: str


@dataclass
class Decision:
    decision: str                     # accept | counter | decline
    kw: float
    reason: str
    prep_kwh: float = 0.0
    rebound_kwh: float = 0.0
    max_recovery_kw: float = 0.0
    predicted: dict[str, Any] = field(default_factory=dict)   # indoor_c_range, battery_min_pct


@dataclass
class Allocation:
    member_id: str
    reduce_kw: float
    note: str = ""


@runtime_checkable
class EnergyModelTool(Protocol):
    name: str

    def forecast(self, ctx: MemberContext, horizon_h: int = 24) -> Forecast:
        """Member side. Today's hourly load, PV and net draw, with a P10-P90 band."""

    def flexibility(self, ctx: MemberContext, window: list[int]) -> Flexibility:
        """Member side. How much the member could reduce or increase in each hour, and what that costs."""

    def decide(self, ctx: MemberContext, reduce_kw: float, window: list[int], price: float) -> Decision:
        """Member side. Accept, counter with a feasible kW, or decline a request."""

    def plan_dispatch(self, offers: list[Any], need_kw: float, window: list[int], price: float,
                      round_no: int, exclude: set[str], committed: dict[str, float]) -> list[Allocation]:
        """Coordinator side. Who to ask for how much this round, from offers only."""
