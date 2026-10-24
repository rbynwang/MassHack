# How we build MassHack with Kiro

Drop this section into the repo README once the project is done, and fill in the screenshots.

## Setup (once per teammate)
1. Install Kiro from kiro.dev/downloads and sign in. Redeem the event code at kiro.dev/redeem.
2. `git clone https://github.com/rbynwang/MassHack.git ~/Documents/MassHack`
3. Unzip `masshack-kiro-setup.zip` (creates the hidden `.kiro/` folder) and `masshack-data-2025-2026.zip` (into `data/`).
4. In Kiro: File → Open Folder → MassHack. Click the Kiro ghost icon in the left sidebar: you should see Specs, Steering and Hooks.

## The loop we follow
1. Open a spec's `tasks.md` (start with `building-world-model`, then `community-simulation`).
2. Click "Start task" above the next unchecked task. Kiro reads the steering files and writes the code.
3. Review the changes, accept, and let the hook run the tests on save.
4. Commit with the task number: `git commit -m "Task 2.1: battery physics + bill (spec building-world-model)"`.
5. Use the chat panel for small edits; use a task for anything in the plan.

## Who does what (suggested)
- Person A: `building-world-model` tasks 1–2 (data, physics, baselines) → checkpoint 12:30.
- Person B: `building-world-model` tasks 3–4 (forecaster, world model, planner).
- Person C: `community-simulation` tasks 1–4 (members, offers, coordinator, trust layer).
- Person D: demo views (both specs, task 6/7) and the pitch.

## What judges see in the repo
- `.kiro/steering/`: product, tech (including the 2025–26 data rule), structure, forecasting rules.
- `.kiro/specs/`: two specs, each requirements → design → tasks, with tasks checked off.
- `.kiro/hooks/`: tests run automatically on every save of model or community code.
- Commit history that follows the task list.
- Screenshots: (1) task list half done, (2) a hook running tests, (3) a spec page.

## Where AI is inside the product
- World model: learns how weather and actions change each building's load and solar.
- Planner: imagines many battery plans and picks the cheapest.
- Coordinator check: the world model predicts the community's load before any command is sent.
- Optional: an LLM explains decisions in plain language using the model's numbers.
