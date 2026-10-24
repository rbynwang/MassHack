"""Loading, cleaning, and train/test splitting of the HouseZero dataset.

All timestamps are kept in UTC internally; convert to America/New_York only
for display.  Power in kW, energy in kWh.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "housezero"
HOURLY_CSV = DATA_DIR / "housezero_hourly.csv"

# Hard cut-off: keep one year for training, hold out the final 2 months.
TRAIN_END = "2026-03-31 23:00:00+00:00"
TEST_START = "2026-04-01 00:00:00+00:00"


def load_hourly(path: Path = HOURLY_CSV) -> pd.DataFrame:
    """Load the joined hourly CSV and apply light cleaning.

    Returns a DataFrame indexed by UTC timestamp.
    """
    df = pd.read_csv(path, parse_dates=["timestamp_utc"], index_col="timestamp_utc")
    df.index = pd.to_datetime(df.index, utc=True)
    df.sort_index(inplace=True)

    # Clip only in features; keep raw columns intact.
    df["pv_total_kw"] = df["pv_total_raw_kw"].clip(lower=0.0)

    # Approximate building demand (kW) = grid net + PV.
    # 'grid_net_kw' is signed: negative = export.
    df["demand_kw"] = df["grid_net_kw"] + df["pv_total_kw"]

    return df


def train_test_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into train and held-out test sets by date."""
    train = df.loc[:TRAIN_END].copy()
    test = df.loc[TEST_START:].copy()
    return train, test


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar and lag features for forecasting."""
    out = df.copy()
    out["hour"] = out.index.hour
    out["dayofweek"] = out.index.dayofweek
    out["month"] = out.index.month
    out["hour_sin"] = np.sin(2 * np.pi * out["hour"] / 24)
    out["hour_cos"] = np.cos(2 * np.pi * out["hour"] / 24)

    # Lag features (1 h and 24 h) for load and PV.
    for col in ("demand_kw", "pv_total_kw"):
        out[f"{col}_lag1"] = out[col].shift(1)
        out[f"{col}_lag24"] = out[col].shift(24)

    return out
