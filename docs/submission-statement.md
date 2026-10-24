# MassWatt — submission statement

**Name:** MassWatt
**Tagline:** An agent network for Massachusetts' energy commons. Every building gets an agent; every neighborhood gets a network.
**Track:** Climate Tech · Challenge C3, "Clean power still has to show up at the peak"

## Short version (~50 words)

MassWatt gives every building its own AI agent and connects those agents through an open protocol. Agents keep their owners' limits private, negotiate with a neighborhood coordinator, and get paid for what they verifiably deliver. Replayed on Massachusetts' 2025 peak day, 19 agents cut the neighborhood's evening peak by 28%.

## Project statement (~250 words)

Massachusetts already has the devices: solar panels, batteries, heat pumps, smart thermostats. What it's missing is the network. Today each building faces the grid alone. When buildings optimize alone, they all react to the same price and create a new peak instead of flattening the old one. Grid programs pay mainly battery and solar owners, and joining means handing your data and device control to a utility or aggregator, so most households, small businesses and public buildings never take part.

MassWatt gives every building its own AI agent. Each agent forecasts its building's load with machine learning trained on Massachusetts data, keeps its owner's comfort and battery limits private, and can accept, counter or decline any request. A neighborhood coordinator negotiates with the agents over a few rounds and staggers them so they don't spike together. A trust guard at each building enforces its limits in code and signs hash-chained receipts, so every payout can be verified. The grid sees the whole neighborhood as one reliable resource.

We replayed June 24, 2025, New England's peak day, for 19 agents in a Cambridge neighborhood: HouseZero's measured building plus homes, shops, a school and a library built from utility load profiles. Acting alone, the neighborhood would peak at 398 kW; together, 286 kW. The grid asks for 60 kW from 5 to 7 PM; the commons pools it in three rounds, pays $113 to 17 of 19 members (including every heat-pump-only home), blocks one request that would break a household's limit, and lets a library join mid-event with no change to the coordinator. All figures are simulated except HouseZero's measured load.

We built it with Kiro: steering docs encode the data rules, the agent network was implemented from a Kiro spec, and property-based tests prove no agent ever exceeds its limits and payouts always add up. They caught a real rounding bug.
