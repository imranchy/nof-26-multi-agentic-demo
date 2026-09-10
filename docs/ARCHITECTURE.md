# Architecture

The demonstrator separates semantic interaction from numerical network truth.

```text
Operator
   |
   v
Mistral semantic coordinator
(intent, references, objectives, constraints, bounded 1-3 step plan)
   |
   +-------------------+-------------------+-------------------+
   |                   |                   |                   |
   v                   v                   v                   v
XGBoost tool       RF SLA tool       PSC policy engine     Temporal tools
traffic forecast   class/probability  PCA / MBA / SAA      compare/range/risk
   |                   |                   |                   |
   +-------------------+-------------------+-------------------+
                               |
                               v
                     deterministic evidence
                               |
                         Mistral explanation
                               |
                        grounding guardrail
                         pass / fallback
```

## Trust boundary

Mistral may interpret language and explain evidence. It does not calculate traffic, SLA probabilities, SC allocation, blocking, reconfiguration, or validation metrics. XGBoost and Random Forest are frozen trained models. PCA/MBA/SAA and KPI calculations are deterministic Python. Unsupported numeric or physical-layer statements are rejected by the grounding guardrail.

## Semantic layer

The coordinator supports arbitrary valid five-minute timestamps, two-time comparisons, ranges, relative follow-ups, policy objectives expressed in natural language, SC constraints, recommendation-change questions, evidence/trust questions, and bounded multi-tool plans. `app/semantic/resolver.py` validates obvious timestamp/objective/constraint language and prevents unsafe defaults from silently changing operator intent.

## Policy metadata vs executable policy

`policies/*.yaml` contains declarative metadata. `config/operator_policy.yaml` contains demonstrator recommendation principles and trust rules. `prompts/operator_skill.md` describes LLM behavior. The executable policy truth remains in `app/policy_engine/*.py`.

## Scope

Physical-layer simulation and fault localization are not implemented because no calibrated GNPy configuration or physical telemetry is available. Generic unrelated requests and physical-layer requests use separate out-of-scope responses.
