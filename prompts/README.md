# NoF prompt modules v1

Coordinator runtime should concatenate:
1. `coordinator/base_v1.md`
2. all coordinator category modules

The coordinator needs all routing categories available before it can classify an operator request.

Explainer runtime should concatenate:
1. `explainer/base_v1.md`
2. the module matching the executed evidence category
3. `operator_style_v1.md`

Suggested evidence-category mapping:
- traffic_forecast -> traffic_prediction_v1.md
- sla_risk_state / sla_explanation -> sla_risk_state_v1.md
- full_network_state -> full_network_state_v1.md
- policy_comparison_balanced -> policy_comparison_balanced_v1.md
- objective_aware_policy -> objective_aware_policy_v1.md
- policy_counterfactual -> policy_counterfactual_v1.md
- sc_constraints -> sc_constraints_v1.md
- temporal_comparison -> temporal_comparison_v1.md
- range_risk_discovery -> range_risk_discovery_v1.md
- conversational_context -> conversational_context_v1.md

All files are v1 so benchmark results remain attributable to one prompt-generation baseline.
