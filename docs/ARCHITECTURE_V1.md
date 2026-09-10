# Architecture v1

Operator language is handled by Mistral as a semantic coordinator and grounded explainer. It does not calculate network values.

Prediction layer -> traffic forecast and SLA/risk state

Deterministic control layer -> PCA, MBA, SAA, blocking/reconfiguration KPIs, temporal comparisons, time-range summaries, and operator SC constraints

Semantic layer -> natural-language intent, timestamps, objectives, policies, constraints, bounded multi-tool planning, and follow-up context

Safety layer -> deterministic route normalization plus numeric, categorical, causal, physical-scope, and implementation-detail grounding checks

Physical-layer analysis, GNPy, RAG, and actuation are deliberately out of scope for v1. They can be added later as new deterministic/knowledge tools without changing the v1 benchmark.
