# Tasks: Commonwatt agent network

- [x] 1. Model tool contract and labeled mock (`tools/contract.py`, `tools/mock.py`) — R2.1, R4.2
- [x] 2. Protocol messages, signed envelope, JSON Schema export (`protocol.py`, `signing.py`) — R1
- [x] 3. Bus with signature check and message log; registry with live join (`network.py`) — R1.2-3, R4.5
- [x] 4. Trust guard and hash-chained ledger (`trust.py`) — R3
- [x] 5. Neighborhood builder from MA data (`members.py`) — R6.3
- [x] 6. Member agent: card, offer, accept/counter/decline, execute (`agents/member.py`) — R2
- [x] 7. Grid agent from ISO-NE data (`agents/grid.py`) — R5
- [x] 8. Coordinator: rounds, stagger, settlement (`agents/coordinator.py`) — R4
- [x] 9. Scenario runner and export (`scenario.py`) — R6.1
- [x] 10. Demo page (`app/`) — R6
- [x] 11. Property-based tests: guard never passes a request over the limit; pooled ≤ accepted; payouts sum to
      settlement; tampered receipt detected — R3, R4.3, R4.6
- [x] 12. Hook: rerun the network tests when `src/commonwatt` changes (`.kiro/hooks/commonwatt-tests-on-save.json`)
- [x] 13. Plug in the trained model: `tools/gridcollective.py` (default tool) calls the GridCollective forecasts and
      battery LP from branch `model/gridcollective`; members it was not trained on fall back to the stand-in — R2.1
