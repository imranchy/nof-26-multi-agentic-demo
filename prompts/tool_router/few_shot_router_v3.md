# Canonical routing examples v3

These examples are intentionally compact and written in English. They teach semantic boundaries, not language-specific phrases. Operator requests may still arrive in any supported language.

## 1. Traffic prediction
User: `What traffic do you expect at 21:15?`
Call: `get_traffic_forecast(time="21:15")`

## 2. SLA risk/state
User: `What is the predicted SLA state at 11:25?`
Call: `get_sla_prediction(time="11:25")`

## 3. Full network state
User: `Show me the complete network state at 16:20.`
Call: `get_network_state_at_time(time="16:20")`

## 4. Balanced policy comparison
User: `Which allocation policy would you use at 17:35?`
Call: `compare_policies_at_time(time="17:35", objective="balanced")`

## 5. Objective-aware policy
User: `At 19:25, minimize blocking.`
Call: `compare_policies_at_time(time="19:25", objective="min_blocking")`

## 6. Named-policy counterfactual
User: `What happens if we use MBA at 13:50?`
Call: `simulate_policy_at_time(time="13:50", policy="MBA")`

## 7. Hard SC constraint
User: `Reserve 1 SC for PON at 10:45.`
Call: `analyze_constrained_allocation(time="10:45", constraints=[{"service":"pon","subcarriers":1}])`

## 8. Conversational follow-up
Previous operator request: `What traffic is forecast at 10:45?`
Current operator request: `At that same time, show the SLA risk.`
Call: `get_sla_prediction()`

## 9. Temporal comparison
User: `What changed between 13:20 and 19:25?`
Call: `compare_network_states(time_a="13:20", time_b="19:25")`

## 10. Ranked interval discovery
User: `Show the two busiest intervals.`
Call: `find_risk_intervals(metric="total_gbps", top_k=2)`

## 11. Continuous range summary
User: `Give me a network summary from 17:00 to 20:30.`
Call: `summarize_time_range(start_time="17:00", end_time="20:30")`

## 12. Out-of-scope boundary
User: `What is the weather today?`
Call: `decline_out_of_scope()`

Physical-layer boundary example:
User: `What is the OSNR at 21:15?`
Call: `decline_physical_layer()`
