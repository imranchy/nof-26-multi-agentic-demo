# Range and risk discovery routing v1

Use the appropriate range/risk capability for requests about:

- highest-risk intervals
- riskiest periods
- busiest or peak-load intervals
- highest blocking intervals
- highest SC-reconfiguration intervals
- summaries across a time range
- extrema or ranked intervals across the day-ahead view

Use the minimum single tool required whenever one capability is sufficient.

## Capability selection

Use `find_risk_intervals` for ranked or extreme intervals.

Use `summarize_time_range` for summaries over a continuous time range.

Do not reduce a time-range summary to endpoint snapshots.

Do not use policy comparison merely because a range request contains an
optimization objective.

## Risk and extrema discovery

Use `find_risk_intervals` when the operator asks where or when a metric is
highest, lowest, busiest, riskiest, or most extreme.

Strong discovery meanings include:

- highest-risk intervals
- riskiest intervals
- riskiest periods
- most at risk
- highest Failure-prone risk
- busiest intervals
- peak-load intervals
- highest-load intervals
- peak traffic
- highest blocking
- most blocking
- highest reconfiguration
- most reconfiguration
- most SC reconfiguration
- highest SC reconfiguration
- most controller churn
- highest controller churn

Examples:

"Find the three highest-risk intervals today."

-> `find_risk_intervals`
-> metric = failure_probability
-> top_k = 3

"Show me the riskiest periods in the day-ahead view."

-> `find_risk_intervals`
-> metric = failure_probability

"Which are the busiest intervals today?"

-> `find_risk_intervals`
-> metric = total_gbps

"Find the intervals with the highest blocking."

-> `find_risk_intervals`
-> metric = blocking

"Where do we see the most SC reconfiguration?"

-> `find_risk_intervals`
-> metric = reconfiguration

"Where is controller churn highest?"

-> `find_risk_intervals`
-> metric = reconfiguration

## Metric extraction

Map the operator's requested quantity to the tool metric exactly.

Use:

- highest-risk
- riskiest
- most at risk
- Failure-prone risk

-> `failure_probability`

Use:

- busiest
- peak load
- highest load
- peak traffic
- highest traffic

-> `total_gbps`

Use:

- highest blocking
- most blocking
- blocking peak

-> `blocking`

Use:

- most reconfiguration
- highest reconfiguration
- SC reconfiguration
- controller churn

-> `reconfiguration`

Do not substitute a different metric because related values may also be
available.

## Top-k extraction

Extract the requested number of intervals when explicitly supplied.

Examples:

"Find the three highest-risk intervals."

-> top_k = 3

"Show the five busiest periods."

-> top_k = 5

"Give me the top 2 blocking intervals."

-> top_k = 2

If no number is explicitly supplied, use the tool default.

Do not invent a top-k value from unrelated numbers.

## Time-range summaries

Use `summarize_time_range` when the operator asks for a summary over a
continuous period.

Strong range-summary meanings include:

- summarize from START to END
- summarise from START to END
- summary from START to END
- summarize between START and END
- summarise between START and END
- network summary between START and END
- summarize the period
- summarize the range
- summarize load, risk and policy behavior
- summarize the network while using an objective

Examples:

"Summarize the network from 18:00 to 22:00."

-> `summarize_time_range`
-> start_time = 18:00
-> end_time = 22:00

"Give me a network summary between 08:00 and 12:00."

-> `summarize_time_range`
-> start_time = 08:00
-> end_time = 12:00

"From 13:00 to 17:00, summarize load, risk and policy behavior."

-> `summarize_time_range`
-> start_time = 13:00
-> end_time = 17:00

"Summarize 19:00 to 23:00 with minimum blocking as the objective."

-> `summarize_time_range`
-> start_time = 19:00
-> end_time = 23:00
-> objective = min_blocking

"Between 00:00 and 06:00, summarize the network while prioritizing stability."

-> `summarize_time_range`
-> start_time = 00:00
-> end_time = 06:00
-> objective = min_reconfiguration

## Range versus endpoint snapshots

A range request must analyze the whole period.

Do not handle:

"Summarize the network from 18:00 to 22:00."

as:

- `get_network_state_at_time` at 18:00
- `get_network_state_at_time` at 22:00

Use:

`summaryze_time_range`

only.

Do not add endpoint snapshots merely to make the answer more complete.

## Range versus cross-time comparison

A summary asks about the behavior of the full range.

A comparison asks how two timestamps differ.

Examples:

"Compare 18:00 and 22:00."

-> `compare_network_states`

"How did the network change between 18:00 and 22:00?"

-> `compare_network_states`

"Summarize the network from 18:00 to 22:00."

-> `summarize_time_range`

"Give me a summary between 08:00 and 12:00."

-> `summarize_time_range`

Do not confuse a range summary with an endpoint comparison.

## Range versus policy comparison

An optimization objective inside a range-summary request is an argument,
not a different intent.

Examples:

"Summarize 19:00 to 23:00 with minimum blocking as the objective."

-> `summarize_time_range`
-> objective = min_blocking

Do NOT route this to `compare_policies_at_time`.

"Between 00:00 and 06:00, summarize the network while prioritizing stability."

-> `summarize_time_range`
-> objective = min_reconfiguration

Do NOT route this to `compare_policies_at_time`.

Use `compare_policies_at_time` only when the operator asks to compare or
recommend policies at one timestamp.

## Objective extraction

For range summaries, preserve the requested objective.

Map:

- minimum blocking
- lowest blocking
- minimize blocking
- minimise blocking

-> `min_blocking`

Map:

- stability
- prioritize stability
- prioritise stability
- prioritizing stability
- prioritising stability
- minimum reconfiguration
- fewest reconfigurations
- minimum churn
- lowest churn

-> `min_reconfiguration`

Map:

- balanced
- trade-off
- compromise

-> `balanced`

Map explicit SLA-priority language to the configured SLA-priority objective.

Do not replace an explicitly requested objective with the default objective.

## Time extraction

For range summaries, extract the start and end timestamps exactly.

Examples:

"from 18:00 to 22:00"

-> start_time = 18:00
-> end_time = 22:00

"between 08:00 and 12:00"

-> start_time = 08:00
-> end_time = 12:00

"19:00 to 23:00"

-> start_time = 19:00
-> end_time = 23:00

Do not treat the end timestamp as a single-time request.

Do not collapse the range into one timestamp.

## Tool boundary

Use one `find_risk_intervals` call for a normal extrema/ranking request.

Use one `summarize_time_range` call for a normal continuous-range summary.

Do not add:

- `get_network_state_at_time`
- `compare_network_states`
- `compare_policies_at_time`
- `get_traffic_forecast`
- `get_sla_prediction`

unless the operator explicitly asks for those additional analyses.

Use the minimum analytical capability needed and stop.