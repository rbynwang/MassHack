---
inclusion: always
---
# Product: Building World Model (MassHack, Track 3 Climate Tech)

## Problem
Small and medium commercial buildings in Massachusetts pay for their highest 15-minute peak each month (demand charge) and are shifting to heat pumps, which moves peaks into cold snaps. Their solar + battery systems run on vendor defaults that ignore the weather, so batteries are often empty when the peak arrives.

## Users
- A building or facilities manager with no energy engineer (primary).
- The utility / ConnectedSolutions program that pays batteries to discharge on peak days (secondary).

## What the product does
1. Learns how weather drives the building's electricity and solar output (world model).
2. Imagines tomorrow under many candidate plans (battery schedule, pre-cool / load-shift mode) and picks the cheapest.
3. Explains the decision in plain language and shows the dollars saved against "no battery" and "vendor default".

## Track fit
- Cleaner, more affordable buildings: lower bills, more self-used solar.
- A more reliable clean energy system: lower peaks on the hottest and coldest days.
- Resilient communities: the battery keeps a reserve ahead of extreme weather.

## Judging criteria we design for
- Potential value: real problem, scalable to any building with an interval meter, plain-language UI.
- Implementation: thoughtful use of Kiro (specs, steering, hooks) and of AI (world model + planner + LLM explanations).
- Quality and design: one polished screen for the demo, consistent colors (grey = without AI, amber = with AI).

## Non-goals today
Real device control, accounts, live utility integrations.
