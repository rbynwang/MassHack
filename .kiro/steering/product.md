# Product

**Commonwatt** — Hackachusetts 2026, Energy & Climate track, challenge C3 ("clean power still has to show
up at the peak").

An agent network that lets a Massachusetts neighborhood turn its homes, businesses and public buildings into an
energy commons. Every building gets an agent; a coordinator per commons negotiates with them; trust guards
enforce each owner's private limits and sign receipts. The grid sees the commons as one reliable resource.

## Split of work
- **ML model and tooling (Robyn):** forecasts and per-building decisions, trained on HouseZero and other MA data.
- **Agent network (Kiro):** protocol, member agents, trust guards, coordinator, grid agent, demo. Agents call the
  model only through `src/commonwatt/tools/contract.py` (`EnergyModelTool`); a labeled mock stands in until the
  trained model is plugged in.

## Demo (one Cambridge neighborhood, June 24, 2025, the ISO-NE peak day)
1. The network forms. 2. Each member optimizes alone and the neighborhood spikes. 3. The grid asks; the
coordinator negotiates; a guard blocks one request. 4. A library joins live. 5. Receipts and earnings by member type.

## Rules
- Massachusetts data only. Do not use out-of-state datasets.
- Every number shown must be labeled measured, simulated or assumption (battery sizes, tariff, prices paid).
- Deadline: submitted on SundAI by **8 PM ET, Oct 24 2026**. Start submitting at 6 PM.
