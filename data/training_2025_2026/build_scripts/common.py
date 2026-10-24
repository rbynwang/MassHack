import os, numpy as np, pandas as pd
S = os.environ.get("MASSHACK_WORK", "work")  # working folder with raw downloads
OUT = os.path.join(S, "unified")
TZ = "America/New_York"
START_L = pd.Timestamp("2025-06-01 00:00", tz=TZ); END_L = pd.Timestamp("2026-06-01 00:00", tz=TZ)
LAT, LON = 42.38, -71.11

def grid_index():
    return pd.date_range(START_L.tz_convert("UTC"), END_L.tz_convert("UTC"), freq="15min", inclusive="left", name="timestamp_utc")

def calendar(idx):
    from pandas.tseries.holiday import USFederalHolidayCalendar
    loc = idx.tz_convert(TZ)
    hol = USFederalHolidayCalendar().holidays("2025-01-01", "2026-12-31")
    d = pd.DataFrame(index=idx)
    d["timestamp_local"] = loc
    d["local_date"] = loc.strftime("%Y-%m-%d")
    d["local_hour"] = loc.hour.astype("int8")
    d["weekday"] = loc.weekday.astype("int8")
    d["us_holiday"] = pd.DatetimeIndex(loc.date).isin(hol)
    return d

def check_window(ts_utc):
    ts = pd.DatetimeIndex(ts_utc)
    assert ts.min() >= START_L.tz_convert("UTC") and ts.max() < END_L.tz_convert("UTC"), (ts.min(), ts.max())
    return str(ts.min()), str(ts.max())
