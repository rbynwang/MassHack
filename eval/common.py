"""Shared split for the evaluation: train / calibration / test by whole weeks (no leakage across days)."""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "eval"))
DATA = os.environ.get("MASSHACK_DATA", str(ROOT / "data" / "model_inputs"))
import sys, numpy as np, pandas as pd
from masshack.data import Dataset

def split(ds):
    tz = ds.weather.index.tz
    all_days = list(pd.date_range(ds.weather.index[0].normalize() + pd.Timedelta("8D"),
                                  ds.weather.index[-1].normalize() - pd.Timedelta("1D"), freq="1D", tz=tz))
    peaks = ds.pick_peak_days()
    test = set()
    for d in peaks.values():
        c = pd.Timestamp(d, tz=tz); test |= {c + pd.Timedelta(days=k) for k in range(-3, 4)}
    test |= {d for d in all_days if 15 <= d.day <= 21}                  # one week per month
    cal = {d for d in all_days if 8 <= d.day <= 14 and d not in test}   # one week per month, for calibration only
    train = [d for d in all_days if d not in test and d not in cal]
    return train, sorted(cal), sorted(d for d in test if d in set(all_days)), peaks

def season(d):
    return "winter" if d.month in (12, 1, 2) else "summer" if d.month in (6, 7, 8) else "shoulder"
