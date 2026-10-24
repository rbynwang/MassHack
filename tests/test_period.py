"""Every exported series must sit inside 2025-05-01 .. 2026-06-01 America/New_York (the team's data rule)."""
from pathlib import Path

import pandas as pd
import pytest

DATA = Path(__file__).resolve().parents[1] / "data" / "model_inputs"
START = pd.Timestamp("2025-05-01", tz="America/New_York").tz_convert("UTC")
END = pd.Timestamp("2026-06-01", tz="America/New_York").tz_convert("UTC")


@pytest.mark.parametrize("name", ["weather.parquet", "grid.parquet", "members_load_2025_2026.parquet"])
def test_period(name):
    p = DATA / name
    if not p.exists():
        pytest.skip(f"{name} not present")
    ts = pd.to_datetime(pd.read_parquet(p, columns=["timestamp_utc"])["timestamp_utc"], utc=True)
    assert ts.min() >= START and ts.max() < END
