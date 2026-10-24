"""Calibration checks from guideline section 5.

Accumulates population statistics batch by batch so the checks scale to
thousands of homes without re-reading the hourly output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from homesim import baseline
from homesim.inputs import Inputs

TEMP_BINS = np.arange(-16, 22, 2.0)


@dataclass
class CalibrationAccumulator:
    n_hours: int
    sum_load_nonhp: np.ndarray = None
    n_nonhp: int = 0
    sum_load_hp: np.ndarray = None
    sum_hpkw_hp: np.ndarray = None
    n_hp: int = 0
    monthly_rows: list = field(default_factory=list)
    solar_midday_net: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.sum_load_nonhp = np.zeros(self.n_hours)
        self.sum_load_hp = np.zeros(self.n_hours)
        self.sum_hpkw_hp = np.zeros(self.n_hours)

    def add(self, homes: pd.DataFrame, inp: Inputs, total: np.ndarray, hp_kw: np.ndarray, net: np.ndarray) -> None:
        is_hp = (homes["heating_type"] == "heat_pump").to_numpy()
        self.sum_load_nonhp += total[~is_hp].sum(axis=0)
        self.n_nonhp += int((~is_hp).sum())
        self.sum_load_hp += total[is_hp].sum(axis=0)
        self.sum_hpkw_hp += hp_kw[is_hp].sum(axis=0)
        self.n_hp += int(is_hp.sum())

        month = inp.frame["timestamp_local"].dt.strftime("%Y-%m").to_numpy()
        months = pd.unique(month)
        m = pd.DataFrame(
            {mo: total[:, month == mo].sum(axis=1) for mo in months}, index=homes["home_id"]
        )
        m["heating_type"] = homes["heating_type"].to_numpy()
        m["has_pv"] = (homes["pv_kw_dc"] > 0).to_numpy()
        self.monthly_rows.append(m)

        loc = inp.frame["timestamp_local"]
        mid = ((loc.dt.hour >= 11) & (loc.dt.hour < 14) & loc.dt.month.isin([4, 5, 6, 7, 8])).to_numpy()
        has_pv = (homes["pv_kw_dc"] > 0).to_numpy()
        if has_pv.any():
            self.solar_midday_net.append(net[has_pv][:, mid].mean(axis=1))


def _shape(series_by_hour: pd.Series) -> pd.Series:
    return series_by_hour / series_by_hour.mean()


def run_checks(acc: CalibrationAccumulator, inp: Inputs, root: Path) -> dict:
    out: dict = {}
    loc = inp.frame["timestamp_local"]
    local_date = loc.dt.tz_localize(None).dt.normalize().to_numpy()
    hour = loc.dt.hour.to_numpy()
    month = loc.dt.month.to_numpy()

    start = str(inp.day_dates.min().date())
    end = str(inp.day_dates.max().date())
    r1 = baseline.national_grid_r1(root, start, end)

    # 1. Population-average hourly shape, non-heat-pump homes vs National Grid R-1.
    if acc.n_nonhp:
        sim = pd.Series(acc.sum_load_nonhp / acc.n_nonhp)
        res = {}
        for label, months in {"all": range(1, 13), "jan_feb": [1, 2], "jul_aug": [7, 8]}.items():
            sel = np.isin(month, list(months))
            s = _shape(sim[sel].groupby(hour[sel]).mean())
            r1_sel = r1[np.isin(r1.index.month, list(months))]
            b = _shape(r1_sel.mean(axis=0))
            res[label] = {
                "pearson_r": round(float(np.corrcoef(s.values, b.values)[0, 1]), 3),
                "max_abs_diff": round(float((s - b).abs().max()), 3),
                "sim_shape": s.round(3).tolist(),
                "r1_shape": b.round(3).tolist(),
            }
        daily_sim = sim.groupby(local_date).sum()
        daily_r1 = r1.sum(axis=1).reindex(daily_sim.index)
        ok = daily_r1.notna()
        res["daily_kwh_pearson_r"] = round(float(np.corrcoef(daily_sim[ok], daily_r1[ok])[0, 1]), 3)
        res["daily_kwh_ratio_sim_over_r1"] = round(float(daily_sim[ok].mean() / daily_r1[ok].mean()), 3)
        out["shape_vs_r1_nonhp"] = res

    # 2. Average monthly use.
    m = pd.concat(acc.monthly_rows)
    # All 13 local months (May 2025 - May 2026) are complete in the HouseZero period.
    full_months = [c for c in m.columns if isinstance(c, str) and c[:2] == "20"]
    per_home_monthly = m[full_months].mean(axis=1)
    rs = baseline.resstock_sfd_per_home(root)
    out["monthly_use"] = {
        "sim_mean_kwh_per_month_all": round(float(per_home_monthly.mean()), 1),
        "sim_mean_kwh_per_month_by_heating": {
            k: round(float(v), 1) for k, v in per_home_monthly.groupby(m["heating_type"]).mean().items()
        },
        "sim_monthly_profile_kwh": {c: round(float(m[c].mean()), 1) for c in full_months},
        "eia_2024_ma_all_households_kwh_per_month": baseline.EIA_MA_2024_AVG_MONTHLY_KWH,
        "resstock_ma_sfd_kwh_per_month_2018_weather": round(rs["annual_kwh"] / 12, 1),
        "r1_kwh_per_month_same_dates": round(float(r1.sum(axis=1).groupby(r1.index.to_period("M")).sum().mean()), 1),
        "pass_above_eia": bool(per_home_monthly.mean() > baseline.EIA_MA_2024_AVG_MONTHLY_KWH),
    }

    # 3. Heat-pump homes peak on cold Jan-Feb mornings.
    if acc.n_hp:
        hp_load = acc.sum_load_hp / acc.n_hp
        top = np.argsort(hp_load)[-max(10, len(hp_load) // 100):]
        in_jf = np.isin(month[top], [1, 2])
        morning = (hour[top] >= 5) & (hour[top] < 10)
        winter = np.isin(month[top], [12, 1, 2])
        out["hp_peaks"] = {
            "n_top_hours": int(len(top)),
            "share_jan_feb": round(float(in_jf.mean()), 3),
            "share_dec_feb": round(float(winter.mean()), 3),
            "share_5_to_10am": round(float(morning.mean()), 3),
            "share_jan_feb_morning": round(float((in_jf & morning).mean()), 3),
            "peak_kw_population_mean": round(float(hp_load.max()), 2),
            "peak_timestamp_local": str(loc.iloc[int(np.argmax(hp_load))]),
        }

        # 5. Heat-pump temperature response vs HouseZero (normalised shape).
        hp_kw = pd.Series(acc.sum_hpkw_hp / acc.n_hp)
        cats = pd.cut(pd.Series(inp.temp_out_c), TEMP_BINS)
        sim_resp = hp_kw.groupby(cats, observed=False).mean()
        hz_resp = baseline.housezero_heat_pump_response(root, TEMP_BINS)
        both = pd.DataFrame({"sim": sim_resp, "hz": hz_resp}).dropna()
        both = both[both.index.map(lambda iv: iv.right <= 16)]  # heating side only
        s_n = both["sim"] / both["sim"].max()
        h_n = both["hz"] / both["hz"].max()
        out["hp_temperature_response"] = {
            "pearson_r_normalised": round(float(np.corrcoef(s_n, h_n)[0, 1]), 3),
            "bins": [str(i) for i in both.index],
            "sim_kw": both["sim"].round(3).tolist(),
            "housezero_kw": both["hz"].round(3).tolist(),
            "note": "HouseZero uses a ground-source heat pump with radiant slabs; compare shape only.",
        }

    # 4. Solar homes export at midday in spring and summer.
    if acc.solar_midday_net:
        net = np.concatenate(acc.solar_midday_net)
        out["solar_midday_export"] = {
            "n_solar_homes": int(len(net)),
            "share_net_exporting_11_to_14_apr_aug": round(float((net < 0).mean()), 3),
            "median_mean_net_kw": round(float(np.median(net)), 3),
        }
    return out


def format_checks(checks: dict) -> str:
    lines = ["Calibration checks (guideline section 5)", "-" * 44]
    s = checks.get("shape_vs_r1_nonhp")
    if s:
        lines.append(
            "1. Shape vs National Grid R-1 (non-HP homes): "
            f"r(all)={s['all']['pearson_r']}, r(Jan-Feb)={s['jan_feb']['pearson_r']}, "
            f"r(Jul-Aug)={s['jul_aug']['pearson_r']}; daily kWh r={s['daily_kwh_pearson_r']}, "
            f"sim/R-1 level={s['daily_kwh_ratio_sim_over_r1']}"
        )
    m = checks["monthly_use"]
    lines.append(
        f"2. Monthly use: sim {m['sim_mean_kwh_per_month_all']} kWh/mo "
        f"(by heating {m['sim_mean_kwh_per_month_by_heating']}); EIA MA all households "
        f"{m['eia_2024_ma_all_households_kwh_per_month']}; R-1 same dates {m['r1_kwh_per_month_same_dates']}; "
        f"ResStock MA SFD {m['resstock_ma_sfd_kwh_per_month_2018_weather']} -> above EIA: {m['pass_above_eia']}"
    )
    p = checks.get("hp_peaks")
    if p:
        lines.append(
            f"3. HP homes top {p['n_top_hours']} hours: {p['share_jan_feb']:.0%} in Jan-Feb, "
            f"{p['share_5_to_10am']:.0%} at 5-10 AM, {p['share_jan_feb_morning']:.0%} both; "
            f"peak {p['peak_kw_population_mean']} kW at {p['peak_timestamp_local']}"
        )
    so = checks.get("solar_midday_export")
    if so:
        lines.append(
            f"4. Solar homes net-exporting 11-14h Apr-Aug: {so['share_net_exporting_11_to_14_apr_aug']:.0%} "
            f"of {so['n_solar_homes']} (median net {so['median_mean_net_kw']} kW)"
        )
    r = checks.get("hp_temperature_response")
    if r:
        lines.append(f"5. HP load vs outdoor temp, shape r vs HouseZero = {r['pearson_r_normalised']} (GSHP reference)")
    return "\n".join(lines)
