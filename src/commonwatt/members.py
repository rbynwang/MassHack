"""The June 24, 2025 neighborhood: 19 members built from Massachusetts data only.

Each member has a `Twin`: a small physical model of the building for the event day (hourly, local hours 0-23).
The twin is the "real building" in the simulation, and the mock model tool reads it as a stand-in for the
trained model. Data labels: measured (HouseZero, BPL shape, ISO-NE), simulated (ComStock-template members,
homesim homes), assumption (batteries not in the data, sizes, costs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from commonwatt import LOCAL_TZ

EVENT_DAY = "2025-06-24"
HOURS = np.arange(24)
ROOT = Path(__file__).resolve().parents[2]
TRAIN = ROOT / "data" / "training_2025_2026"

SOC_MAX = 0.90                 # batteries are charged to at most 90 % (assumption)
SOC_DEFAULT_PV = 0.90          # a battery with solar is full by late afternoon on a sunny day (assumption)
SOC_DEFAULT_GRID = 0.50        # a battery without solar sits at 50 % (assumption)
RULE_SHED_FRAC = 0.30          # HVAC can shed 30 % of its cooling power for up to 3 h (assumption)
RULE_PREP = 0.5                # pre-cool energy per kWh shed (assumption)
RULE_REBOUND = 0.6             # rebound energy per kWh shed (assumption)
HVAC_SHARE_ASSUMED = 0.30      # cooling share of summer load where the data has no cooling column (assumption)
TOU_PEAK = list(range(16, 21)) # the time-of-use peak every member reacts to when alone (assumption)


def cop_cool(t_out_c: np.ndarray) -> np.ndarray:
    return np.clip(4.5 - 0.1 * (t_out_c - 25.0), 2.0, 4.5)


@dataclass
class HomeThermal:
    """One-node thermal model of a home (homesim parameters), hourly."""
    ua: float
    cap: float
    cool_cap_kw: float
    setpoint_c: np.ndarray       # cooling setpoint per hour (inf = cooling off)
    band_c: float                # comfort band, private to the owner
    t_out_c: np.ndarray
    gains_kw: np.ndarray         # internal + solar gains
    t0_c: float

    def run(self, offset_c: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Cooling electricity (kW) and indoor temperature (start of hour) for setpoint + offset."""
        sp = self.setpoint_c + offset_c
        cop = cop_cool(self.t_out_c)
        T = self.t0_c
        elec, tin = np.zeros(24), np.zeros(24)
        for h in range(24):
            tin[h] = T
            t_free = T + (self.ua * (self.t_out_c[h] - T) + self.gains_kw[h]) / self.cap
            need = max(0.0, self.cap * (t_free - sp[h])) if np.isfinite(sp[h]) else 0.0
            q = min(need, self.cool_cap_kw)
            elec[h] = q / cop[h]
            T = t_free - q / self.cap
        return elec, tin


@dataclass
class Plan:
    """What a member would do to hold `kw` less for every hour of `window`."""
    kw: float                    # feasible reduction held in every window hour
    battery_kw: float
    thermal_kw: float
    fixed_delta_kw: np.ndarray   # thermal change in every hour (pre-cool +, shed -, rebound +)
    battery_prep_kwh: float      # pre-charge needed before the window (schedulable)
    battery_recovery_kwh: float  # recharge after the window (schedulable)
    battery_max_kw: float
    indoor_c: np.ndarray | None
    battery_min_pct: float | None


@dataclass
class Twin:
    member_id: str
    display_name: str
    kind: str                    # large_building | household | small_business | public_institution
    label: str                   # measured | simulated | assumption
    source: str
    owner: str
    load_kw: np.ndarray          # gross load with no optimization
    pv_kw: np.ndarray
    cooling_kw: np.ndarray       # electric cooling inside load_kw
    t_out_c: np.ndarray
    battery: dict | None = None  # kwh, kw, eff_rt, reserve_pct, label
    home: HomeThermal | None = None
    precool_delta_kw: np.ndarray | None = None   # business pre-cool mode minus baseline (training data)
    cost_per_kwh: float = 0.10   # member's own cost of shifting a kWh (assumption)
    assets: list[str] = field(default_factory=list)
    model_id: str | None = None  # the building's id in the trained GridCollective model, if it has one

    # ---------------------------------------------------------------- basics
    @property
    def planned_kw(self) -> np.ndarray:
        return self.load_kw - self.pv_kw

    def _soc_default(self) -> float:
        return SOC_DEFAULT_PV if self.pv_kw.max() > 0.5 else SOC_DEFAULT_GRID

    # ---------------------------------------------------------------- thermal
    def _home_plan(self, delta_c: float, window: list[int]) -> tuple[np.ndarray, np.ndarray]:
        """Pre-cool by delta in the 2 h before the window, raise by delta in the window."""
        off = np.zeros(24)
        w0, w1 = min(window), max(window)
        off[max(0, w0 - 2):w0] = -delta_c
        off[window] = +delta_c
        for k, f in enumerate((0.67, 0.33), start=1):       # ease back to the setpoint over 2 h (spreads rebound)
            if w1 + k < 24:
                off[w1 + k] = f * delta_c
        base, _ = self.home.run(np.zeros(24))
        elec, tin = self.home.run(off)
        return elec - base, tin

    def _thermal(self, kw: float, window: list[int]) -> tuple[float, np.ndarray, np.ndarray | None]:
        """Largest thermal reduction <= kw held over the window, with its profile change."""
        if self.home is not None:
            def red(d):
                dlt, _ = self._home_plan(d, window)
                return float(-dlt[window].max()) if len(window) else 0.0   # held in every hour: worst hour
            lo, hi = 0.0, self.home.band_c
            if red(hi) <= kw:
                d = hi
            else:
                for _ in range(25):
                    mid = 0.5 * (lo + hi)
                    lo, hi = (mid, hi) if red(mid) < kw else (lo, mid)
                d = lo
            dlt, tin = self._home_plan(d, window)
            return max(0.0, red(d)), dlt, tin
        cap = RULE_SHED_FRAC * self.cooling_kw[window]
        if len(window) > 3 or cap.size == 0:
            return 0.0, np.zeros(24), None
        k = float(min(kw, cap.min()))
        dlt = np.zeros(24)
        if k > 0:
            e = k * len(window)
            w0, w1 = min(window), max(window)
            dlt[window] = -k
            dlt[max(0, w0 - 2):w0] += RULE_PREP * e / 2
            n_after = min(24, w1 + 5) - (w1 + 1)
            if n_after > 0:
                dlt[w1 + 1:w1 + 1 + n_after] += RULE_REBOUND * e / n_after   # HVAC eases back over 4 h
        return k, dlt, None

    # ---------------------------------------------------------------- battery
    def _battery_sustain(self, n_hours: int) -> float:
        b = self.battery
        if not b or n_hours == 0:
            return 0.0
        usable = (SOC_MAX - b["reserve_pct"] / 100) * b["kwh"] * b["eff_rt"] ** 0.5
        return float(min(b["kw"], usable / n_hours))

    def _battery_energy(self, kw: float, n_hours: int) -> tuple[float, float, float]:
        """Prep kWh, recovery kWh and minimum SOC % for discharging kw over n_hours."""
        b = self.battery
        eta = b["eff_rt"] ** 0.5
        drop = kw * n_hours / eta / b["kwh"]
        s0 = self._soc_default()
        s_window = max(s0, b["reserve_pct"] / 100 + drop)
        prep = max(0.0, s_window - s0) * b["kwh"] / eta
        after = s_window - drop
        recovery = max(0.0, s0 - after) * b["kwh"] / eta
        return prep, recovery, 100 * after

    # ---------------------------------------------------------------- what the agent and tools use
    def capability(self, window: list[int]) -> dict:
        per_hour = {}
        for h in window:
            bat = self._battery_sustain(1)
            th, _, _ = self._thermal(1e9, [h])
            per_hour[h] = round(bat + th, 2)
        p = self.plan(1e9, window)
        e = p.kw * len(window)
        inc = {h: round(self.battery["kw"], 2) if self.battery else 0.0 for h in window}
        prep = (p.battery_prep_kwh + float(np.clip(p.fixed_delta_kw[:min(window)], 0, None).sum())) / e if e else 0.0
        reb = (p.battery_recovery_kwh + float(np.clip(p.fixed_delta_kw[max(window) + 1:], 0, None).sum())) / e if e else 0.0
        return {"per_hour": per_hour, "increase": inc, "sustain": round(p.kw, 2), "prep_ratio": round(prep, 3),
                "rebound_ratio": round(reb, 3), "max_recovery_kw": round(p.battery_max_kw, 2)}

    def plan(self, kw: float, window: list[int]) -> Plan:
        n = len(window)
        bat = min(kw, self._battery_sustain(n))
        th, dlt, tin = self._thermal(max(0.0, kw - bat), window)
        prep = rec = 0.0
        soc_min = None
        if self.battery:
            prep, rec, soc_min = self._battery_energy(bat, n) if bat > 0 else (0.0, 0.0, 100 * self._soc_default())
        if tin is None and self.home is not None:
            _, tin = self.home.run(np.zeros(24))
        return Plan(kw=round(bat + th, 3), battery_kw=bat, thermal_kw=th, fixed_delta_kw=dlt,
                    battery_prep_kwh=prep, battery_recovery_kwh=rec,
                    battery_max_kw=self.battery["kw"] if self.battery else 0.0,
                    indoor_c=tin, battery_min_pct=soc_min)

    def execute(self, plan: Plan, window: list[int], prep_kw: dict[int, float],
                recovery_kw: dict[int, float]) -> np.ndarray:
        """Actual net draw (kW) for an assignment: thermal change + battery discharge, prep and recovery."""
        net = self.planned_kw + plan.fixed_delta_kw
        net[window] -= plan.battery_kw
        for h, v in {**prep_kw}.items():
            net[h] += v
        for h, v in recovery_kw.items():
            net[h] += v
        return net

    def alone(self) -> np.ndarray:
        """Each member optimizing alone against the same time-of-use peak (16-21 h)."""
        net = self.planned_kw.copy()
        if self.home is not None:
            off = np.zeros(24)
            off[14:16] = -self.home.band_c
            off[16:21] = +self.home.band_c
            base, _ = self.home.run(np.zeros(24))
            elec, _ = self.home.run(off)
            net += elec - base
        if self.precool_delta_kw is not None:
            net += self.precool_delta_kw
        if self.battery:
            b, eta = self.battery, self.battery["eff_rt"] ** 0.5
            soc = SOC_DEFAULT_GRID if self.pv_kw.max() > 0.5 else self._soc_default()
            lo, s0 = b["reserve_pct"] / 100, self._soc_default()
            for h in range(24):
                if net[h] < 0 and soc < SOC_MAX:                      # store own solar surplus
                    c = min(b["kw"], -net[h], (SOC_MAX - soc) * b["kwh"] / eta)
                    soc += c * eta / b["kwh"]; net[h] += c
                elif h in TOU_PEAK and net[h] > 0 and soc > lo:       # cover own load in the peak
                    d = min(b["kw"], net[h], (soc - lo) * b["kwh"] * eta)
                    soc -= d / eta / b["kwh"]; net[h] -= d
                elif h >= 21 and soc < s0:                            # recharge when the cheap rate starts
                    c = min(b["kw"], (s0 - soc) * b["kwh"] / eta)
                    soc += c * eta / b["kwh"]; net[h] += c
        return net

    def indoor_baseline_c(self) -> np.ndarray | None:
        return None if self.home is None else self.home.run(np.zeros(24))[1]


# ====================================================================== builders
def _local_day(df: pd.DataFrame, col: str = "timestamp_utc") -> pd.DataFrame:
    df = df.copy()
    df[col] = pd.to_datetime(df[col], utc=True)
    df = df.set_index(col).tz_convert(LOCAL_TZ)
    return df.loc[EVENT_DAY]


def _weather() -> pd.DataFrame:
    w = _local_day(pd.read_parquet(TRAIN / "weather.parquet"))
    h = w[["outdoor_temp_c", "ghi_w_m2", "pv_per_kwdc"]].resample("h").mean(numeric_only=True)
    return pd.DataFrame({"temp_out_c": h["outdoor_temp_c"].to_numpy(), "solar_w_m2": h["ghi_w_m2"].to_numpy(),
                         "pv_per_kwdc": h["pv_per_kwdc"].to_numpy()}, index=range(24))


def _training_members(ids: list[str]) -> dict[str, dict[str, pd.DataFrame]]:
    ml = pd.read_parquet(TRAIN / "members_load_2025_2026.parquet", filters=[("member_id", "in", ids)])
    ml = _local_day(ml)
    out: dict[str, dict[str, pd.DataFrame]] = {}
    for (m, mode), g in ml.groupby(["member_id", "mode"]):
        out.setdefault(m, {})[mode] = g[["demand_kw", "pv_kw", "cooling_kw"]].resample("h").mean().reset_index(drop=True)
    return out


BUSINESS = [  # member_id, display, kind, battery?, cost
    ("cs_27764", "office_01", "large_building", True, 0.12),
    ("cs_54098", "office_02", "large_building", False, 0.12),
    ("cs_38689", "office_03", "large_building", False, 0.12),
    ("cs_16530", "shop_01", "small_business", False, 0.20),
    ("cs_903", "shop_02", "small_business", False, 0.20),
    ("cs_25407", "restaurant_01", "small_business", False, 1.50),   # dinner service: shifting costs more
]


def _business_twins(weather: pd.DataFrame) -> list[Twin]:
    meta = pd.read_csv(TRAIN / "members.csv").set_index("member_id")
    data = _training_members([b[0] for b in BUSINESS] + ["hz_main"])
    twins = []
    t_out = weather["temp_out_c"].to_numpy()
    hz = data["hz_main"]["baseline"]
    m = meta.loc["hz_main"]
    twins.append(Twin(
        member_id="housezero", display_name="HouseZero", kind="large_building", label="measured",
        source="HouseZero 2025-26 measured load and PV (Harvard CGBC); battery hypothetical (members.csv)",
        owner="Harvard CGBC", load_kw=hz["demand_kw"].to_numpy(), pv_kw=hz["pv_kw"].fillna(0).to_numpy(),
        cooling_kw=np.zeros(24), t_out_c=t_out,
        battery={"kwh": float(m.battery_kwh), "kw": float(m.battery_kw), "eff_rt": 0.90, "reserve_pct": 20.0,
                 "label": "assumption"},
        cost_per_kwh=0.06, assets=["pv", "battery", "heat_pump"], model_id="hz_main"))
    for mid, name, kind, has_bat, cost in BUSINESS:
        d, m = data[mid], meta.loc[mid]
        base = d["baseline"].copy()
        pre = d.get("precool_42")
        if base["cooling_kw"].fillna(0).max() < 0.5:     # no cooling column in the template data
            base["cooling_kw"] = HVAC_SHARE_ASSUMED * base["demand_kw"]
        twins.append(Twin(
            member_id=name, display_name=name.replace("_", " ").title(), kind=kind, label="simulated",
            source=f"ComStock {m.building_type} template driven by HouseZero 2025-26 weather ({mid})",
            owner=f"{m.building_type} owner", load_kw=base["demand_kw"].to_numpy(),
            pv_kw=base["pv_kw"].fillna(0).to_numpy(), cooling_kw=base["cooling_kw"].fillna(0).to_numpy(),
            t_out_c=t_out,
            battery=({"kwh": float(m.battery_kwh), "kw": float(m.battery_kw), "eff_rt": 0.90, "reserve_pct": 15.0,
                      "label": "assumption"} if has_bat else None),
            precool_delta_kw=(pre["demand_kw"] - base["demand_kw"]).to_numpy() if pre is not None else None,
            cost_per_kwh=cost, assets=(["pv", "battery", "hvac"] if has_bat else ["pv", "hvac"]), model_id=mid))
    return twins


def _household_twins() -> list[Twin]:
    from homesim import load_config
    from homesim.behavior import simulate_behavior
    from homesim.inputs import load_inputs
    from homesim.physics import simulate_physics
    from homesim.population import sample_homes

    cfg = load_config()
    inp = load_inputs(cfg, ROOT)
    rng = np.random.default_rng(2025)
    homes = sample_homes(cfg, 160, "balanced", rng)
    pv_bat = homes[(homes.pv_kw_dc > 0) & (homes.battery_kwh > 0) & (homes.n_ev == 0)].head(5)
    hp_only = homes[(homes.heating_type == "heat_pump") & (homes.pv_kw_dc == 0) & (homes.battery_kwh == 0)
                    & (homes.n_ev == 0)].head(5)
    chosen = pd.concat([pv_bat, hp_only]).reset_index(drop=True)
    beh = simulate_behavior(cfg, chosen, inp, np.random.default_rng(7))
    phy = simulate_physics(cfg, chosen, inp, beh)
    loc = inp.frame["timestamp_local"]
    idx = np.flatnonzero((loc.dt.strftime("%Y-%m-%d") == EVENT_DAY).to_numpy())
    t_out = inp.temp_out_c[idx]
    solar = inp.solar_w_m2[idx]
    twins = []
    for i, h in chosen.iterrows():
        gains = beh.internal_gain_kw[i, idx] + solar / 1000.0 * h.window_aperture_m2
        sp = beh.cool_setpoint_c[i, idx]
        home = HomeThermal(ua=h.ua_kw_per_c, cap=h.capacitance_kwh_per_c, cool_cap_kw=h.cooling_capacity_kw,
                           setpoint_c=sp, band_c=float(h.comfort_band_c), t_out_c=t_out, gains_kw=gains,
                           t0_c=float(phy.t_in_c[i, idx[0]]))
        cool, _ = home.run(np.zeros(24))
        base = beh.base_kw[i, idx]
        has_bat = h.battery_kwh > 0
        n = len(twins) + 1
        twins.append(Twin(
            member_id=f"home_{n:02d}", display_name=f"Home {n:02d}", kind="household", label="simulated",
            source=f"homesim {h.home_type} ({h.archetype}, {int(h.sqft)} sq ft), HouseZero weather, R-1 calibrated",
            owner="household", load_kw=base + cool, pv_kw=phy.pv_kw[i, idx], cooling_kw=cool, t_out_c=t_out,
            battery=({"kwh": float(h.battery_kwh), "kw": float(h.battery_kw), "eff_rt": float(h.battery_eff),
                      "reserve_pct": float(h.battery_reserve_pct), "label": "assumption"} if has_bat else None),
            home=home, cost_per_kwh=0.06 if has_bat else 0.15,
            assets=(["pv", "battery", h.cooling_type] if has_bat else ["heat_pump"])))
    return twins


def _ng_class_day(rate: str, day: str) -> np.ndarray:
    ng = pd.read_excel(ROOT / "data/baseline/raw/nationalgrid_meco_load_shapes.xlsx", sheet_name="MECO ALL")
    ng = ng[ng["Rate"].astype(str).str.strip() == rate]
    ng["Date"] = pd.to_datetime(ng["Date"])
    return ng[ng["Date"] == day].iloc[0, 2:26].astype(float).to_numpy()


def _mild_reference(series_by_day: pd.DataFrame, weather_days: pd.Series) -> np.ndarray:
    """Average weekday shape on mild days (daily mean 12-18 C) in May-June 2025: no cooling."""
    mild = weather_days[(weather_days > 12) & (weather_days < 18)].index
    rows = series_by_day.loc[series_by_day.index.isin(mild)]
    rows = rows[pd.to_datetime(rows.index).dayofweek < 5]
    return rows.mean(axis=0).to_numpy()


def _public_twins(weather: pd.DataFrame) -> list[Twin]:
    t_out = weather["temp_out_c"].to_numpy()
    hz = pd.read_csv(ROOT / "data/housezero/housezero_hourly.csv", parse_dates=["timestamp_utc"])
    hz["loc"] = hz.timestamp_utc.dt.tz_convert(LOCAL_TZ)
    hz = hz[(hz["loc"] >= "2025-05-01") & (hz["loc"] < "2025-07-01")]
    temp_days = hz.groupby(hz["loc"].dt.strftime("%Y-%m-%d"))["outdoor_temperature_c"].mean()

    # School: National Grid G-2 (general service, demand) class shape, scaled to a 60 kW school.
    ng = pd.read_excel(ROOT / "data/baseline/raw/nationalgrid_meco_load_shapes.xlsx", sheet_name="MECO ALL")
    ng = ng[ng["Rate"].astype(str).str.strip() == "G-2"]
    ng["Date"] = pd.to_datetime(ng["Date"]).dt.strftime("%Y-%m-%d")
    g2 = ng.set_index("Date").iloc[:, 1:25].astype(float)
    g2.columns = range(24)
    hot = g2.loc[EVENT_DAY].to_numpy()
    mild = _mild_reference(g2, temp_days)
    scale = 60.0 / hot.max()
    school_pv = 40.0 * weather["pv_per_kwdc"].fillna(0).to_numpy()
    school = Twin(
        member_id="school_01", display_name="School 01", kind="public_institution", label="assumption",
        source="National Grid G-2 class shape for 2025-06-24 scaled to 60 kW; 40 kW PV and shared battery assumed",
        owner="Town school department", load_kw=hot * scale, pv_kw=school_pv,
        cooling_kw=np.clip(hot - mild, 0, None) * scale, t_out_c=t_out,
        battery={"kwh": 100.0, "kw": 50.0, "eff_rt": 0.90, "reserve_pct": 20.0, "label": "assumption"},
        cost_per_kwh=0.05, assets=["pv", "shared_battery", "hvac"])

    # Library: Boston Public Library (Central) measured shape, scaled to a 45 kW branch library.
    b = pd.read_csv(ROOT / "data/boston_public_library/bpl_hourly.csv", parse_dates=["timestamp_utc"])
    b["loc"] = b.timestamp_utc.dt.tz_convert(LOCAL_TZ)
    b = b[b.quality_flag == "complete"]
    b["day"], b["h"] = b["loc"].dt.strftime("%Y-%m-%d"), b["loc"].dt.hour
    piv = b.pivot_table(index="day", columns="h", values="mean_kw_available")
    hot = piv.loc[EVENT_DAY].to_numpy()
    scale = 45.0 / hot.max()
    library = Twin(
        member_id="library_01", display_name="Library 01", kind="public_institution", label="measured",
        source="Boston Public Library Central, measured 2025-06-24 shape, scaled to a 45 kW branch; "
               "HVAC share 30 % assumed",
        owner="City library", load_kw=hot * scale, pv_kw=np.zeros(24),
        cooling_kw=HVAC_SHARE_ASSUMED * hot * scale, t_out_c=t_out, cost_per_kwh=0.08, assets=["hvac"])
    return [school, library]


def build_neighborhood() -> tuple[list[Twin], pd.DataFrame]:
    weather = _weather()
    twins = _business_twins(weather) + _household_twins() + _public_twins(weather)
    return twins, weather
