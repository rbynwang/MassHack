# Commonwatt agent network: run it, and plug in the trained model

## Run

```bash
uv sync
uv run commonwatt-demo            # prints the message log, writes app/data/demo.js and protocol/schemas/*.json
open app/index.html               # the demo page; works offline (Plotly is in app/vendor)
uv run pytest -q tests/test_commonwatt.py
```

Options: `--ask-kw 60` (size of the grid ask), `--window 17,18` (local hours, 5-7 PM), `--tool module:Class`.
Open `app/index.html#all` to show the whole day at once.

## What runs

| Agent | Code | Calls the model for |
|---|---|---|
| Grid agent | `src/commonwatt/agents/grid.py` | — (ISO-NE RT LMP .Z.NEMASSBOST and system load, June 24, 2025) |
| Coordinator | `src/commonwatt/agents/coordinator.py` | `plan_dispatch` (offers only) |
| Trust guard (one per member) | `src/commonwatt/trust.py` | — (owner limits, plan check, delivery, signed receipts, hash chain) |
| Member agent (19) | `src/commonwatt/agents/member.py` | `forecast`, `flexibility`, `decide` (its own data only) |

Messages: `src/commonwatt/protocol.py` (7 types, JSON Schemas in `protocol/schemas/`). Every message is an
Ed25519-signed envelope checked on arrival (`network.py`).

## The trained model is the default tool

`commonwatt.tools.gridcollective:GridCollectiveTool` (default) wraps the GridCollective model from branch
`model/gridcollective` (commit 0b73567): its calibrated LightGBM P10/P50/P90 forecasts for June 24, 2025
(`data/gridcollective/forecast_cache.pkl`) and its battery planner (`src/gridcollective/optimizer.py`, HiGHS LP
with the G-2 demand charge). Member agents that exist in the trained model (HouseZero, the three offices, the two
shops, the restaurant) forecast and price every request with it; homes, the school and library_01 are not in the
trained model and use the labeled stand-in. Every call is listed in `demo.json` under `tool_calls`.
Use the stand-in only: `COMMONWATT_TOOL=commonwatt.tools.mock:MockModelTool uv run commonwatt-demo`.

## Plug in another model

Write a class with the four methods in `src/commonwatt/tools/contract.py` and run with it:

```python
# e.g. src/mlmodel/tool.py
from commonwatt.tools.contract import Decision, Flexibility, Forecast, MemberContext
from commonwatt.tools.mock import MockModelTool

class TrainedModelTool(MockModelTool):          # inherit what is not ready yet
    name = "trained model v1"

    def forecast(self, ctx: MemberContext, horizon_h: int = 24) -> Forecast:
        # ctx.history: past hourly meter readings (load_kw, pv_kw, net_kw, temp_out_c), local time
        # ctx.weather_today: 24 rows (temp_out_c, solar_w_m2); ctx.assets: battery and equipment
        ...
```

```bash
COMMONWATT_TOOL=mlmodel.tool:TrainedModelTool uv run commonwatt-demo
```

| Method | Side | Input | Must return |
|---|---|---|---|
| `forecast(ctx, horizon_h)` | member | its own context | hourly `load_kw`, `pv_kw`, `net_kw`, P10/P90 |
| `flexibility(ctx, window)` | member | its own context | `can_reduce_kw` per hour, `sustain_reduce_kw` for the whole window, prep and rebound kWh per kWh, `cost_per_kwh` |
| `decide(ctx, reduce_kw, window, price)` | member | a request | `accept` / `counter` (kW it can hold for every window hour) / `decline`. Optional `predicted`: `indoor_c_range`, `battery_min_pct`, `fixed_kw` (otherwise the simulated building supplies them) |
| `plan_dispatch(offers, need_kw, window, price, round_no, exclude, committed)` | coordinator | offers only | who to ask for how much this round |

Rules the tests check (`tests/test_commonwatt.py`): an accepted or countered kW must be one the member can hold;
the guard blocks anything over the owner's limit; batteries stay above the reserve; payouts add up.

The mock (`tools/mock.py`) is a perfect-foresight stand-in: it reads each member's digital twin
(`members.py`). Whatever tool decides, the twin is the simulated building that carries out the committed kW,
and its trust guard checks the result (battery reserve, comfort band) before it runs. The demo page shows the
tool's name, so judges can see which one produced the numbers.

## Data (Massachusetts only)

| Member | Source | Label |
|---|---|---|
| HouseZero | `data/training_2025_2026` `hz_main` load and PV | measured (battery assumed) |
| 3 offices, 2 shops, 1 restaurant | `data/training_2025_2026` ComStock-template members on HouseZero weather | simulated |
| 10 households (5 solar + battery, 5 heat pump only) | `src/homesim`, calibrated to National Grid R-1 | simulated |
| School 01 | National Grid G-2 class shape for the date, scaled to 60 kW; PV and shared battery assumed | assumption |
| Library 01 (joins live) | Boston Public Library Central measured shape, scaled to 45 kW | measured shape |
| Grid | ISO-NE real-time LMP and system load | measured |

Assumptions: batteries not in the data, the 4-9 PM time-of-use peak every member reacts to when alone, the price
paid (Boston-zone real-time price averaged over the window), comfort costs, a 30 % HVAC share where the data has
no cooling column. Results are simulation outputs, not measured savings.
