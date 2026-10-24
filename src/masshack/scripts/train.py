"""Train the Path 1 forecaster (and optionally the Path 2 world model).

Usage:
    uv run masshack-train
"""

from __future__ import annotations

import argparse

from masshack.data import load_hourly, make_features, train_test_split
from masshack.forecast import QuantileForecaster


def main() -> None:
    parser = argparse.ArgumentParser(description="Train MassHack forecaster.")
    parser.add_argument(
        "--path",
        choices=["forecast", "world-model"],
        default="forecast",
        help="Which model to train (Path 1 forecaster or Path 2 world model).",
    )
    args = parser.parse_args()

    df = load_hourly()
    feats = make_features(df)
    train, _ = train_test_split(feats)

    if args.path == "forecast":
        print(f"Training LightGBM quantile forecaster on {len(train)} rows...")
        model = QuantileForecaster().fit(train)
        print(f"Done. Trained {len(model.models)} models.")
    else:
        print("World model training not yet wired up (Path 2 stretch goal).")


if __name__ == "__main__":
    main()
