---
inclusion: fileMatch
fileMatchPattern: ["model/**/*.py", "tests/**/*.py"]
---
# Forecasting and evaluation rules

- No leakage: a decision made at time t may only use observations up to t and the weather *forecast* for later times. On historical data, simulate the forecast as measured weather plus noise (temperature N(0, 1.5 °C) per day, irradiance scaled by a random cloud factor); never feed future measured weather as if known.
- Split by time, never randomly. Hold out the hottest summer weeks and the coldest winter weeks as the test set.
- Every strategy is scored on the same days with the same tariff: no battery, vendor default (self-consumption), time-of-use rule, world model + planner, perfect-foresight optimum (cvxpy).
- Headline metric: share of the perfect-foresight saving captured, split into energy $ and demand-charge $.
- Forecast metrics: MAE and P10–P90 coverage against a seasonal-naive baseline; ablation without weather inputs.
