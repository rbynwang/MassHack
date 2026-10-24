# Tech stack

- **Python 3.12+**, managed with `uv` (`uv add <pkg>`, `uv run <script>`).
- Data: `pandas`, `numpy`. Read `.csv.gz` directly with pandas.
- Path 1 (fallback): `lightgbm` quantile forecasts + `cvxpy` linear program,
  re-solved every 15 min over a 24 h horizon.
- Path 2 (pitch): `torch` — encoder + EMA target + action-conditioned predictor
  (JEPA-style loss) + read-out heads, ~200k params, trains on a Mac (CPU/MPS).
  Planner: CEM over 256 plans inside the model's imagination.
- Battery SOC, efficiency and the tariff are **exact equations**, never learned.
- Frontend: a single static page (HTML + JS, Plotly or D3), reading JSON that
  Python exports. No build step unless clearly needed.
- Tests: `pytest`, with `hypothesis` for property-based tests on the battery
  and tariff math (e.g. SOC stays within [0, capacity]; bill is never negative
  energy cost for zero import).

## Constraints
- Must run offline on one MacBook; no paid APIs required for the core demo.
- Keep training under ~10 minutes.
- Do not commit large derived files (> 50 MB) or model checkpoints; regenerate them.
