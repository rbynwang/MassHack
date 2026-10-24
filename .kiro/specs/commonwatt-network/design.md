# Design: Commonwatt agent network

## Layers
```
Grid agent (ISO-NE prices/load)  --ask-->  Coordinator (one per commons)  --request-->  Trust guard  -->  Member agent
                                  <--pooled--                             <--response--               <--   (calls the model tool)
Registry: agent cards + public keys          Ledger: hash-chained signed receipts          Bus: in-memory, logs every message
```

## Code (`src/commonwatt/`)
| Module | Role |
|---|---|
| `protocol.py` | Pydantic models for the 7 messages + signed `Envelope`; `export_schemas()` writes `protocol/schemas/*.json` |
| `signing.py` | Ed25519 over canonical JSON |
| `network.py` | `Bus` (delivery, signature check, message log), `Registry` (agent cards, keys, live join) |
| `trust.py` | `TrustGuard` (owner's private limits, request/plan checks, delivery measurement, receipts), `Ledger` |
| `tools/contract.py` | **The interface to Robyn's model**: `EnergyModelTool` with `forecast`, `flexibility`, `decide`, `plan_dispatch` |
| `tools/mock.py` | `MockModelTool`: labeled stand-in until the trained model is plugged in |
| `members.py` | Builds the June 24, 2025 neighborhood from MA data |
| `agents/member.py`, `agents/coordinator.py`, `agents/grid.py` | The agents |
| `scenario.py` | Runs no-optimization / alone / network, exports `app/data/demo.js` |

## The model tool (swap point)
```python
class EnergyModelTool(Protocol):
    def forecast(self, ctx: MemberContext, horizon_h: int = 24) -> Forecast: ...
    def flexibility(self, ctx: MemberContext, window: list[int]) -> Flexibility: ...
    def decide(self, ctx: MemberContext, request: Request, limits: Stagger) -> Decision: ...
    def plan_dispatch(self, offers: list[Offer], ask: Ask, commons_kw: list[float]) -> list[Allocation]: ...
```
Member-side methods run inside each member agent with that member's `MemberContext` (meter history, assets,
weather forecast). The coordinator-side method sees offers only. Select the implementation with
`COMMONWATT_TOOL=module:Class` (default `commonwatt.tools.mock:MockModelTool`).

## Data (Massachusetts only, 2025-06-24, hourly, local hours 0-23)
| Member | Source | Kind |
|---|---|---|
| HouseZero | `data/training_2025_2026` `hz_main` (measured) | measured |
| 3 offices, 3 small businesses | `data/training_2025_2026` ComStock-template members (HouseZero weather) | simulated |
| 10 households | `src/homesim` (calibrated to National Grid R-1, HouseZero weather) | simulated |
| School | National Grid G-2 class shape for the date, scaled | assumption on size |
| Library (joins live) | Boston Public Library Central measured shape, scaled to a branch | measured shape |
| Grid | ISO-NE RT LMP .Z.NEMASSBOST and system load | measured |

## Scenarios
- **No optimization:** recorded loads, batteries idle, thermostats at setpoint.
- **Alone:** each member reacts to the same time-of-use peak (16:00-21:00, assumption): batteries discharge in the
  peak and recharge at 21:00; homes pre-cool before 16:00 and recover at 21:00; businesses run their pre-cool mode.
- **Network:** grid ask for 17:00-19:00; negotiation; preparation and recovery staggered by valley filling.

## Negotiation
Round 1 requests use per-hour offers (cheapest first, +10 % margin). Members counter when they cannot sustain the
kW for the whole window. Guards block requests above the owner's current limit. Round 2 reassigns the gap,
including members that joined after round 1. Round 3 is a last top-up.
