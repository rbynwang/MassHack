# Requirements: Commonwatt agent network

Scope for Hackachusetts 2026 (Oct 24). The ML model (forecasts and per-building decisions) is built by
Robyn; this spec covers the agent network that calls it. Massachusetts data only.

## R1 Protocol
**User story:** As any building owner, I want my agent to join a commons by speaking an open message format,
so no coordinator code changes when a new member joins.
1. THE protocol SHALL define seven message types: `agent_card`, `ask`, `offer`, `request`, `response`,
   `assignment`, `receipt`, and export each as JSON Schema.
2. WHEN any agent sends a message THE network SHALL carry it in an envelope signed with the sender's Ed25519 key.
3. WHEN a message's signature does not match the sender's registered key THE receiver SHALL reject it.
4. An `offer` SHALL carry only `hour`, `planned_kw`, `can_reduce_kw`, `can_increase_kw`, `cost_per_kwh`
   (plus rebound and preparation energy), never raw meter data or private limits.

## R2 Member agents
**User story:** As a member, I want my agent to forecast my needs, offer flexibility and decide for itself.
1. Each member agent SHALL call the model tool (`EnergyModelTool`) for its forecast, flexibility and decisions,
   passing only its own data.
2. WHEN it receives a request THE member agent SHALL answer `accept`, `counter` (with a feasible kW) or `decline`.
3. WHEN a request cannot be sustained for the whole window THE agent SHALL counter with the kW it can sustain.
4. WHEN the price is below its cost THE agent SHALL decline.

## R3 Trust guard
**User story:** As a member, I want requests checked against my private limits in code, so the coordinator never
needs to see them.
1. THE guard SHALL block any request above the owner's current kW limit or outside the owner's allowed hours,
   and say why.
2. THE guard SHALL check the agent's planned action (battery reserve, comfort band) before it runs.
3. WHEN the window ends THE guard SHALL measure delivery against the member's own no-event forecast and sign a
   receipt; receipts SHALL form a hash chain so any change is detectable.

## R4 Coordinator (dispatch agent, one per commons)
**User story:** As the grid, I want the commons to answer an ask as one reliable resource.
1. WHEN an ask arrives THE coordinator SHALL collect offers and run up to three negotiation rounds, reassigning
   gaps left by counters, declines and blocks.
2. THE coordinator SHALL call the model tool's `plan_dispatch` with offers only.
3. THE pooled commitment SHALL never exceed the sum of accepted amounts.
4. THE coordinator SHALL stagger preparation (pre-cool, pre-charge) and recovery (recharge, rebound) so the
   commons' peak outside the window does not exceed its no-event peak where possible.
5. WHEN a new agent card is registered during negotiation THE coordinator SHALL include it in the next round.
6. Payouts SHALL sum to the settled earnings.

## R5 Grid agent
1. THE grid agent SHALL build the ask from ISO-NE data for .Z.NEMASSBOST on 2025-06-24 (window, price).

## R6 Demo
1. THE demo SHALL compare commons load for: no optimization, each member alone, and the Commonwatt network.
2. THE demo SHALL show the message log, a live join, a blocked request, member receipts and earnings by
   member type, working offline in a browser.
3. Every number SHALL be labeled measured, simulated or assumption.
