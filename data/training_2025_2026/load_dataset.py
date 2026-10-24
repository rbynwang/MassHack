"""Tiny loader for the MassHack 2025-26 unified data layer. All frames: tz-aware UTC DatetimeIndex (interval START)."""
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent

def _ts(df, col="timestamp_utc"):
    df[col] = pd.to_datetime(df[col], utc=True)
    return df.set_index(col).sort_index()

def load_weather():
    """HouseZero measured weather 2025-06-01..2026-06-01 local + solar zenith + pv_per_kwdc (kW per kWdc)."""
    return _ts(pd.read_parquet(HERE / "weather.parquet"))

def load_grid():
    """ISO-NE RT LMP (.Z.NEMASSBOST, $/MWh) + system load (MW), stress/spike/DR flags."""
    return _ts(pd.read_parquet(HERE / "grid.parquet"))

def load_members():
    """One row per member (index member_id)."""
    return pd.read_csv(HERE / "members.csv", dtype={"zip": str}).set_index("member_id")

def load_member_loads(member_id=None, mode=None):
    """Long table: member_id, mode, demand_kw, pv_kw, hvac_kw, cooling_kw, heating_kw, source."""
    filt = []
    if member_id is not None: filt.append(("member_id", "in", [member_id] if isinstance(member_id, str) else list(member_id)))
    if mode is not None: filt.append(("mode", "in", [mode] if isinstance(mode, str) else list(mode)))
    return _ts(pd.read_parquet(HERE / "members_load_2025_2026.parquet", filters=filt or None))

def load_dr_events():
    d = pd.read_csv(HERE / "dr_events_2025.csv")
    for c in ("start_utc", "end_utc"): d[c] = pd.to_datetime(d[c], utc=True)
    return d

def load_stock():
    """BERDO 2025 stock by zip x archetype (not a time series; returned with a plain index)."""
    return pd.read_csv(HERE / "boston_stock.csv", dtype={"zip": str})

if __name__ == "__main__":
    w, g, m = load_weather(), load_grid(), load_members()
    x = load_member_loads("hz_main", "baseline")
    print(w.index.min(), w.index.max(), len(w), len(g), len(m), x.demand_kw.sum() / 4)
