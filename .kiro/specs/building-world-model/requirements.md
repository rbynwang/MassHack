# Requirements: Building World Model

## Introduction
A climate-aware decision system for a small or medium commercial building in Massachusetts with solar and a battery. It learns how weather drives electricity use and solar output, imagines tomorrow under several candidate plans, picks the cheapest, and shows the saving against doing nothing and against the vendor's default battery setting.

## Requirement 1: Climate-aware forecast
**User story:** As a building manager, I want tomorrow's electricity use and solar output predicted from the weather forecast, so that I can see the expensive hours coming.

Acceptance criteria
1. WHEN given the last 24 hours of load, solar and weather plus a 24-hour weather forecast, THE SYSTEM SHALL predict load and solar for the next 96 fifteen-minute steps (24 hourly steps for HouseZero) with P10, P50 and P90 values.
2. THE SYSTEM SHALL use only information available at decision time (no future measured weather).
3. ON held-out hot and cold weeks, THE SYSTEM SHALL report MAE and P10–P90 coverage against a seasonal-naive forecast, and the error increase when weather inputs are removed.

## Requirement 2: Decision by imagination (world model + planner)
**User story:** As a building manager, I want the system to try many plans before acting, so that the battery is full when the peak arrives.

Acceptance criteria
1. THE SYSTEM SHALL evaluate at least 64 candidate plans per decision by rolling the world model forward, combining it with exact battery physics and the tariff.
2. THE SYSTEM SHALL choose the plan with the lowest expected bill (energy + demand charge − demand-response payment) while keeping battery state of charge within its limits and a reserve before forecast peaks.
3. THE SYSTEM SHALL re-plan every step and execute only the first action (receding horizon).
4. WHERE a member supports building modes, THE SYSTEM SHALL also choose among them: template members none / thermostat load shift / pre-cool; HouseZero none / thermal pre-heat / HVAC curtail (with rebound).

## Requirement 3: Proof of value
**User story:** As a judge or a building owner, I want one clear number, so that I know whether this is worth it.

Acceptance criteria
1. THE SYSTEM SHALL score five strategies on the same days with the same tariff: no battery, vendor default, time-of-use rule, world model, perfect-foresight optimum.
2. THE SYSTEM SHALL report $ saved per month, peak kW avoided, and the share of the perfect-foresight saving captured.
3. THE SYSTEM SHALL report results separately for the hottest summer days and the coldest winter days.

## Requirement 4: Demo experience
**User story:** As a building manager with no energy background, I want to see and understand the decision in under a minute.

Acceptance criteria
1. THE DEMO SHALL show a day view: grey line without AI, amber line with AI, faint lines for imagined plans, and the monthly peak line.
2. THE DEMO SHALL let the viewer push the temperature up or down and see the plan and the saving update.
3. THE DEMO SHALL explain each decision in one plain sentence with its dollar value.
4. THE DEMO SHALL run offline from exported JSON.
