# Implementation plan

Depends on spec `building-world-model`. Status key: [x] built and tested in the starter code, [ ] open for the team in Kiro.
Module names in the starter code: `masshack/agents.py`, `coordinator.py`, `trust.py`, `simulate.py`, `boston.py`.

- [x] 1. Members and limits
  - [x] 1.1 Members with roles (prosumer: solar + battery; flex: building modes) and default limits (`agents.build_agents`). _Requirements: 1.1, 4.1_
  - [x] 1.2 Winter and summer peak days from ISO-NE load (`Dataset.pick_peak_days`). _Requirements: 1.3_
- [x] 2. Offers
  - [x] 2.1 Battery flex offers from headroom vs the member's own plan, priced by re-solving its LP. _Requirements: 2.1, 2.2_
  - [x] 2.2 Building-mode offers with rebound. _Requirements: 2.2, 2.3_
- [x] 3. Coordinator
  - [x] 3.1 Grid signals (use less / soak up) and merit-order assignment. _Requirements: 3.1, 3.3_
  - [x] 3.2 Rebound check that rejects assignments creating a new community peak. _Requirements: 3.2_
- [x] 4. Trust layer
  - [x] 4.1 Limits check blocks out-of-bounds commands; tested. _Requirements: 4.1, 4.2_
  - [x] 4.2 Ed25519 signed, hash-chained receipts with verification; tested. _Requirements: 4.3_
  - [x] 4.3 Pro-rata settlement after cost reimbursement; tested. _Requirements: 4.4_
- [x] 5. Run a day: `simulate.simulate_day` for both peak days, realized with actual 2025–26 data. _Requirements: 1.2, 3.3_
- [x] 6. Boston projection by zip with adoption 0–50% (`boston.py`). _Requirements: 5.1–5.4_
- [x] 7. Demo views: community layers, hour inspector with receipts, Boston zip ranking. _Requirements: 6.1–6.3_
- [x] 9. Two-round coordination: price signal on the community's planned peak hours, re-plan capped at each member's solo peak and at its solo import in those hours (`simulate.py`).
- [x] 10. Public-mission rules: heat warning (forecast high ≥ 32.2 °C) makes cooling centers hold 50% battery and refuse building modes; fire/police hold 80%; museums battery only.
- [ ] 8. Next steps for the team (run in Kiro)
  - [ ] 8.1 Boston zip map: add ZIP boundaries GeoJSON from Analyze Boston and color by kW avoided. _Requirements: 6.2_
  - [ ] 8.2 Let members choose their own limits in the demo (slider for max kW and minimum battery charge) and show refused commands live. _Requirements: 4.1, 4.2_
  - [ ] 8.3 Run all 40 summer event days, not only the peak day, and report a season total. _Requirements: 5.3_
  - [ ] 8.4 Add a "verify receipt" button that checks a signature in the browser. _Requirements: 4.3_
