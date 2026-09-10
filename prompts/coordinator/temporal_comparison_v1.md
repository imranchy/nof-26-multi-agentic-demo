# Temporal comparison routing v1

Use `compare_network_states` when the operator asks to compare two specific
timestamps, asks what changed between them, or asks which of the two network
states looks better, worse, or healthier.

A two-time comparison should normally use one `compare_network_states` call.
Do not retrieve both endpoint states separately when the comparison capability
already answers the request.

## Core routing rule

Route to `compare_network_states` when:

1. two distinct timestamps are explicitly given or unambiguously resolved, and
2. the operator asks for comparison, difference, change, better/worse, or
   healthier/riskier behavior between those two times.

Strong comparison meanings include:

- compare TIME_A and TIME_B
- compare TIME_A with TIME_B
- difference between TIME_A and TIME_B
- what changed between TIME_A and TIME_B
- change from TIME_A to TIME_B
- healthier than
- better at ... than ...
- worse at ... than ...
- how different
- versus
- vs

## Direct examples

"Compare the network at 18:10 and 21:15."

-> `compare_network_states`
-> time_a = 18:10
-> time_b = 21:15

"Was 18:10 healthier than 21:15?"

-> `compare_network_states`
-> time_a = 18:10
-> time_b = 21:15

"What changed between 09:30 and 14:05?"

-> `compare_network_states`
-> time_a = 09:30
-> time_b = 14:05

"Compare 07:45 with 16:20."

-> `compare_network_states`
-> time_a = 07:45
-> time_b = 16:20

"How different is the network at 23:10 versus 12:35?"

-> `compare_network_states`
-> time_a = 23:10
-> time_b = 12:35

"Which looks worse, 20:00 or 05:55?"

-> `compare_network_states`
-> time_a = 20:00
-> time_b = 05:55

"Show the change from 11:00 to 13:00."

-> `compare_network_states`
-> time_a = 11:00
-> time_b = 13:00

"Compare traffic and risk at 15:15 and 19:45."

-> `compare_network_states`
-> time_a = 15:15
-> time_b = 19:45

"Was the network better at 06:30 than at 22:30?"

-> `compare_network_states`
-> time_a = 06:30
-> time_b = 22:30

"What is the difference between the 10:10 and 17:40 operator states?"

-> `compare_network_states`
-> time_a = 10:10
-> time_b = 17:40

## Timestamp ordering

Preserve the order in which the operator presents the two timestamps.

The first referenced timestamp is `time_a`.
The second referenced timestamp is `time_b`.

Do not reverse them merely because one occurs later in the day.

Example:

"How different is the network at 23:10 versus 12:35?"

-> time_a = 23:10
-> time_b = 12:35

## Comparison versus range summary

A two-time comparison evaluates two endpoint states.
A range summary analyzes all intervals in a continuous period.

"What changed between 09:30 and 14:05?"

-> `compare_network_states`

"Summarize the network from 09:30 to 14:05."

-> `summarize_time_range`

The words "summarize", "summary", "over the period", or explicit range-summary
semantics favor `summarize_time_range`.

The words "compare", "difference", "changed between", "better", "worse",
"healthier", or "versus" favor `compare_network_states`.

## Minimum single tool

Do not decompose a normal two-time comparison into:

- `get_network_state_at_time` for time A
- `get_network_state_at_time` for time B
- `compare_network_states`

Use only:

`compare_network_states`

when it fully answers the request.

## Tool boundary

Do not use policy comparison merely because policy information may appear in the
network states.

Do not use separate traffic or SLA tools merely because the operator asks to
compare traffic and risk; `compare_network_states` is the bounded comparison
capability for those two timestamps.

Extract both timestamps and stop.
