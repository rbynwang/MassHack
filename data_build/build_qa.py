"""Coverage check of every exported time series + data_quality.json."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import json, glob
rep = {"window_local": [str(START_L), str(END_L)], "files": {}}
for f in sorted(glob.glob(os.path.join(OUT, "*"))):
    name = os.path.basename(f); info = {"bytes": os.path.getsize(f)}
    if f.endswith(".parquet"):
        d = pd.read_parquet(f); info["rows"] = len(d); info["cols"] = len(d.columns)
        tsc = pd.to_datetime(d.timestamp_utc, utc=True)
        info["min_local"] = str(tsc.min().tz_convert(TZ)); info["max_local_interval_start"] = str(tsc.max().tz_convert(TZ))
        info["inside_window"] = bool(tsc.min() >= START_L and tsc.max() < END_L)
        info["null_frac"] = {c: round(float(d[c].isna().mean()), 4) for c in d.columns if d[c].isna().any()}
    elif f.endswith(".csv"):
        d = pd.read_csv(f, low_memory=False); info["rows"] = len(d)
        for c in d.columns:
            if c.endswith("_utc") or c.endswith("_local") or c == "date":
                t = pd.to_datetime(d[c], utc=True); info["inside_window"] = bool(t.min() >= START_L and t.max() <= END_L)
                info[f"{c}_range"] = [str(t.min()), str(t.max())]
    rep["files"][name] = info
for r in glob.glob(os.path.join(S, "unified_build/_*_report.json")):
    rep[os.path.basename(r)[1:-12]] = json.load(open(r))
# no 2018 anywhere in exported time stamps
rep["all_timeseries_inside_window"] = all(v.get("inside_window", True) for v in rep["files"].values())
json.dump(rep, open(os.path.join(OUT, "data_quality.json"), "w"), indent=1, default=str)
for k, v in rep["files"].items(): print(k, v.get("rows"), v["bytes"], v.get("inside_window"), v.get("min_local",""), v.get("max_local_interval_start",""))
print("ALL INSIDE:", rep["all_timeseries_inside_window"])
