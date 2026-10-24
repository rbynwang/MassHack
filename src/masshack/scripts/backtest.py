"""Backtest battery dispatch on the held-out test period.

Compares three strategies on each test day:
  - no battery (baseline bill)
  - vendor-default rule
  - our LP-optimised plan

IMPORTANT: backtests must never use future weather or load as if known.
Use a forecast proxy (persistence or noised actuals) and say so.

Usage:
    uv run masshack-backtest
"""

from __future__ import annotations

import argparse

import numpy as np

from masshack.battery import compute_bill
from masshack.data import load_hourly, make_features, train_test_split
from masshack.planner import lp_plan, vendor_default_actions


def _day_slices(test_df) -> list:
    """Yield (date, DataFrame) for each complete 24-h day in the test set."""
    groups = []
    for date, day in test_df.groupby(test_df.index.date):
        if len(day) == 24:
            groups.append((date, day))
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest MassHack dispatch.")
    parser.add_argument(
        "--forecast",
        choices=["persistence", "perfect"],
        default="persistence",
        help="Forecast proxy. 'perfect' is an upper bound only; label it as such.",
    )
    args = parser.parse_args()

    df = load_hourly()
    feats = make_features(df)
    _, test = train_test_split(feats)

    results = []
    for date, day in _day_slices(test):
        load_kw = day["demand_kw"].to_numpy()
        pv_kw = day["pv_total_kw"].to_numpy()
        hours = day.index.hour.to_numpy()
        weekdays = day.index.dayofweek.to_numpy()

        # Forecast proxy
        if args.forecast == "persistence":
            # Use previous-day actuals as the "forecast" (no future leakage).
            load_fc = np.roll(load_kw, 24) if len(load_kw) >= 24 else load_kw
            pv_fc = np.roll(pv_kw, 24) if len(pv_kw) >= 24 else pv_kw
        else:
            load_fc, pv_fc = load_kw, pv_kw  # upper bound only

        # Baseline: no battery
        base = compute_bill(load_kw - pv_kw, hours, weekdays)

        # Vendor default
        vendor_actions = vendor_default_actions(len(load_kw))
        vendor_grid = load_kw - pv_kw + vendor_actions
        vendor = compute_bill(vendor_grid, hours, weekdays)

        # Our LP plan (uses forecast, evaluated on actuals)
        try:
            plan = lp_plan(load_fc, pv_fc, hours, weekdays)
            ours_grid = load_kw - pv_kw + plan["actions_kw"]
            ours = compute_bill(ours_grid, hours, weekdays)
        except RuntimeError as exc:
            print(f"  {date}: LP failed ({exc}); skipping")
            continue

        results.append(
            {
                "date": str(date),
                "no_battery": base["total_cost"],
                "vendor": vendor["total_cost"],
                "ours": ours["total_cost"],
            }
        )

    if not results:
        print("No complete test days found.")
        return

    import statistics

    saving_vs_none = statistics.mean(r["no_battery"] - r["ours"] for r in results)
    saving_vs_vendor = statistics.mean(r["vendor"] - r["ours"] for r in results)
    print(f"Backtested {len(results)} days (forecast={args.forecast}).")
    print(f"  Mean saving vs. no battery : ${saving_vs_none:.2f}/day")
    print(f"  Mean saving vs. vendor     : ${saving_vs_vendor:.2f}/day")


if __name__ == "__main__":
    main()
