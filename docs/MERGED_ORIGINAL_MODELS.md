# Original-model merged build

This repository keeps the trained XGBoost and Random Forest artifacts and source/prepared datasets from the original `nof-26-multi-agentic-demo-main` repository while applying the updated operator UI, semantic coordinator, deterministic PCA/MBA/SAA policy engine, temporal tools, guardrails, and validation suite.

The live traffic path intentionally does not compare the original model against a separately generated forecast-baseline file at startup. The original model and its matching training/data pipeline are treated as the live source of truth.

Validated locally in the build environment:
- 33 deterministic tests pass.
- Live 21:15 traffic: Enterprise 4.66 Gbps, RAN 45.17 Gbps, PON 38.66 Gbps, total 88.50 Gbps.
- Live 21:15 SLA state: failure-prone, Failure-prone risk 88%.
- Balanced policy recommendation at 21:15: SAA.
- `RAN=2 SC` constrained allocation is feasible at 21:15.
