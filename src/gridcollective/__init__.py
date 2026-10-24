"""GridCollective model (branch `model/gridcollective`, commit 0b73567), the parts the Commonwatt agents call.

- `optimizer.py`, `physics.py`: the battery planner (HiGHS linear program with demand charge, forced import
  changes for "what does it cost you to change your import at hour h?") and exact battery/bill physics. Copied
  unchanged from `masshack/` on that branch.
- `data/gridcollective/forecast_cache.pkl`: the trained forecaster's outputs for the two peak days (calibrated
  LightGBM P10/P50/P90 baseline + action effects for 116 buildings), written by that branch's `run_all.py`.
  Its own `run_all.py --reuse` serves forecasts from the same cache.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "gridcollective" / "forecast_cache.pkl"
MEMBERS_CSV = ROOT / "data" / "gridcollective" / "members.csv"
SOURCE_COMMIT = "0b73567"
