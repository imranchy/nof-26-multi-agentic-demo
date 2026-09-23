# Targeted routing examples v3.1

These examples are intentionally compact and written in English. They teach the semantic distinctions that remain difficult for the router. Concrete values are examples only; extract the actual values from the operator request.

## Traffic prediction
User: `What traffic do you expect at 21:15?`
Call: `get_traffic_forecast(time="21:15")`

## SLA risk/state
User: `What is the predicted SLA state at 11:25?`
Call: `get_sla_prediction(time="11:25")`

## Full network state
User: `Show me the complete network state at 16:20.`
Call: `get_network_state_at_time(time="16:20")`

## Balanced policy comparison
User: `Which allocation policy would you use at 17:35?`
Call: `compare_policies_at_time(time="17:35", objective="balanced")`

User: `Choose the overall allocation strategy at 21:15.`
Call: `compare_policies_at_time(time="21:15", objective="balanced")`

User: `Which of PCA, MBA, and SAA should be used at 18:10?`
Call: `compare_policies_at_time(time="18:10", objective="balanced")`

Contrast:
User: `Reserve 2 SCs for RAN at 17:35.`
Call: `analyze_constrained_allocation(time="17:35", ran_subcarriers=2)`

## Objective-aware policy
User: `At 19:25, favor the lowest blocking.`
Call: `compare_policies_at_time(time="19:25", objective="min_blocking")`

User: `At 20:00, minimize blocking.`
Call: `compare_policies_at_time(time="20:00", objective="min_blocking")`

User: `At 18:10, minimize reconfigurations.`
Call: `compare_policies_at_time(time="18:10", objective="min_reconfiguration")`

Contrast:
User: `Keep RAN on 2 SCs at 19:25.`
Call: `analyze_constrained_allocation(time="19:25", ran_subcarriers=2)`

## Named-policy counterfactual
User: `What happens if we use PCA at 21:15?`
Call: `simulate_policy_at_time(time="21:15", policy="PCA")`

User: `Show the MBA outcome at 13:50.`
Call: `simulate_policy_at_time(time="13:50", policy="MBA")`

## Hard SC constraint
User: `Keep RAN on 2 SCs at 19:00.`
Call: `analyze_constrained_allocation(time="19:00", ran_subcarriers=2)`

User: `Reserve 1 SC for PON at 10:45.`
Call: `analyze_constrained_allocation(time="10:45", pon_subcarriers=1)`

## Conversational follow-up
Previous operator request: `What traffic do you expect at 10:45?`
Current operator request: `At that same time, show the SLA risk.`
Call: `get_sla_prediction()`

Previous operator request: `Keep RAN on 2 SCs at 19:00.`
Current operator request: `Also reserve one SC for PON.`
Call: `analyze_constrained_allocation(pon_subcarriers=1)`

## Temporal comparison
User: `What changed between 13:20 and 19:25?`
Call: `compare_network_states(time_a="13:20", time_b="19:25")`

## Ranked interval discovery
User: `Find the three highest-risk intervals today.`
Call: `find_risk_intervals(metric="failure_probability", top_k=3)`

User: `Show the two busiest intervals.`
Call: `find_risk_intervals(metric="total_gbps", top_k=2)`

## Continuous range summary
User: `Summarize network behavior from 17:00 to 20:30.`
Call: `summarize_time_range(start_time="17:00", end_time="20:30")`

## Out-of-scope boundary
User: `Book a hotel for tonight.`
Call: `decline_out_of_scope()`

User: `Send an email to my colleague.`
Call: `decline_out_of_scope()`

User: `What's the weather tomorrow?`
Call: `decline_out_of_scope()`

## Physical-layer boundary
User: `What is the OSNR at 21:15?`
Call: `decline_physical_layer()`
