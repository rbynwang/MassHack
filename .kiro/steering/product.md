# Product

**MassHack World Model** — Hackachusetts 2026, Energy & Climate track.

A small, climate-aware world model for a building with solar and a battery. It
learns how weather drives the building's power, imagines tomorrow's cost under
many battery plans, executes the cheapest, then checks reality against its
imagination. Full pitch: `proposal/world-model-proposal.html`.

## Research question
How much of the best possible bill saving can a climate-aware world model
capture, compared with the battery setting most installers ship, especially on
the hot days that set the monthly demand peak?

## Demo (2 minutes, one building, one hot day)
- **A · Imagine before acting** (core): fan of imagined battery plans, cheapest
  highlighted, then the real day overlaid. Ends on $ saved vs. no battery and
  vs. the vendor default.
- **B · Heatwave stress test** (climax): temperature slider; vendor battery is
  empty at the 4–6 pm peak, ours held its charge.
- **C · What the model learned** (insight): each day as a dot in the learned
  embedding, colored by temperature.
- D (climate-to-cost curve) and E (chat "ask the building") are stretch goals.

## Priorities for a one-day hack
1. A working end-to-end demo on recorded data beats a better model that is not
   wired up. Build path 1 (forecast + optimizer) first as the fallback.
2. Every number shown to judges must be traceable to the data or to stated
   assumptions (tariff, battery size).
3. Deadline: submitted on SundAI by **8 PM ET, Oct 24 2026**. Start submitting at 6 PM.
