"""Diagnostic plot for one home: a winter week and a summer week (build order step 1)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


def plot_home_weeks(hourly: pd.DataFrame, home: pd.Series, out_png: Path,
                    winter_start: str = "2026-01-19", summer_start: str = "2025-07-21") -> None:
    """hourly: one home's rows indexed by local timestamp."""
    fig, axes = plt.subplots(2, 2, figsize=(15, 8), sharex="col",
                             gridspec_kw={"height_ratios": [1, 1.4]})
    for col, (label, start) in enumerate([("Winter week", winter_start), ("Summer week", summer_start)]):
        s = pd.Timestamp(start, tz=hourly.index.tz)
        w = hourly.loc[s: s + pd.Timedelta(days=7)]
        ax = axes[0, col]
        ax.plot(w.index, w["temp_out_c"], label="outdoor", color="tab:blue")
        ax.plot(w.index, w["t_in_c"], label="indoor", color="tab:red")
        ax.set_ylabel("°C")
        ax.set_title(f"{label} from {start}")
        ax.legend(loc="upper right")
        ax = axes[1, col]
        stack = ["base_kw", "heat_pump_kw", "backup_heat_kw", "ac_kw", "blower_kw", "ev_kw"]
        ax.stackplot(w.index, *[w[c] for c in stack], labels=stack, alpha=0.8)
        ax.plot(w.index, w["pv_kw"], color="gold", lw=1.5, label="pv_kw")
        ax.plot(w.index, w["grid_net_kw"], color="black", lw=0.8, label="grid_net_kw")
        ax.axhline(0, color="grey", lw=0.5)
        ax.set_ylabel("kW")
        ax.legend(loc="upper right", fontsize=7, ncol=2)
    fig.suptitle(
        f"{home['home_id']} · {home['home_type']} · {home['archetype']} · {int(home['sqft'])} sq ft "
        f"{home['vintage']} · UA {home['ua_kw_per_c']:.2f} kW/°C · τ {home['tau_h']:.0f} h  (synthetic)"
    )
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)
