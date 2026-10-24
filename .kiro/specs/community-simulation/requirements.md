# Requirements: Boston Community Simulation

## Introduction
A community of Boston buildings (116 members: HouseZero and the Boston Public Library Central Library (both measured), 25 civic buildings (schools, libraries, community centers, fire and police stations, museums, courthouse offices), 9 large retail, 40 small businesses (NREL ComStock designs driven by HouseZero's measured weather) and 40 homes (synthetic, homesim)) works as one collective. Every hour of a simulated day, each member forecasts, plans its own battery, and offers flexibility; a coordinator assigns tasks when the grid needs help; every action is checked against the member's limits and earns a signed receipt; revenue is split by contribution. The result is then scaled across Boston by zip code to show what the collective would do for the city.

## Requirement 1: Members and forecasts
**User story:** As the coordinator, I want a forecast for every member and for the grid, so that I know when help is needed and who can help.

1. THE SYSTEM SHALL load members from `members.csv` and their 2025–26 loads from `members_load_2025_2026.parquet` via `data/load_dataset.py`.
2. EACH hour, THE SYSTEM SHALL forecast each member's demand and PV for the next 24 hours using the world model from spec `building-world-model` (LightGBM fallback allowed).
3. THE SYSTEM SHALL mark grid-need hours from `grid.parquet` (`grid_stress`, `price_spike`) and `dr_events_2025.csv`.

## Requirement 2: Self-interested plans and flexibility offers
**User story:** As a member, I want my battery planned for my own bill first, and to offer only the extra help I can give.

1. EACH prosumer agent SHALL plan its own battery to minimize its bill (energy + demand charge) within battery limits.
2. EACH member SHALL report, for every grid-need hour, how many kW it can reduce or add beyond its own plan and the cost of doing so (lost bill savings + comfort penalty for building modes).
3. WHERE a member's mode has a rebound (for example `precool_42` raises the midday load, `hvac_curtail` returns the energy in the next hours), THE offer SHALL include that rebound as part of its cost.

## Requirement 3: Coordinator decision
**User story:** As the coordinator, I want to buy the cheapest reliable help first.

1. THE coordinator SHALL assign tasks in order of cost per kW until the target reduction is met or offers run out.
2. BEFORE sending, THE coordinator SHALL use the world model to predict the community's total load after the assignment, including rebound, and reject an assignment that creates a new community peak.
3. THE SYSTEM SHALL log every decision with the numbers that justified it.

## Requirement 4: Trust layer
**User story:** As a member, I want proof that the coordinator never exceeds what I allowed.

1. EACH member SHALL have limits: max kW change, minimum battery state of charge, indoor comfort band, allowed hours.
2. ANY command outside a member's limits SHALL be blocked in code and logged as refused.
3. EACH executed action SHALL produce a receipt (member, hour, kW promised, kW delivered, payment) signed with the coordinator's Ed25519 key and verifiable by the member.
4. REVENUE SHALL be split pro rata to delivered kW during grid-need hours, using the ConnectedSolutions rate assumption ($200/kW-season, labeled as an assumption).

## Requirement 5: Boston projection
**User story:** As a city or utility planner, I want to see what the collective could do across Boston.

1. THE SYSTEM SHALL scale archetype results to each zip using `boston_stock.csv` (counts, floor area, 2025 kWh).
2. THE SYSTEM SHALL support adoption levels 0%, 10%, 20%, 30%, 50%.
3. THE SYSTEM SHALL report, per zip and citywide, peak kW avoided and dollars saved on one winter peak day and one summer peak day.
4. THE SYSTEM SHALL label results as a projection and show which inputs are measured, projected or synthetic.

## Requirement 6: Demo
1. THE DEMO SHALL show a community view: offers → assignments → receipts for one grid-need hour.
2. THE DEMO SHALL show a Boston map (or ranked zip list if the map file is missing) colored by peak kW avoided, with an adoption slider.
3. THE DEMO SHALL run offline from exported JSON.
