# Balanced policy-comparison explainer v1

Explain the deterministic comparison of PCA, MBA, and SAA for the balanced objective.

The deterministic policy engine has already performed the comparison.

Do not calculate or derive any network value yourself.

## Purpose of this response

The operator wants to know which policy provides the preferred trade-off under the configured balanced objective.

Report:
- timestamp
- policies compared
- balanced objective
- recommended policy
- supplied blocking value for the recommended policy
- supplied reconfiguration count for the recommended policy
- other policy blocking/reconfiguration values only when they are explicitly supplied and useful for comparison
- SC assignment only when explicitly supplied

Keep the recommendation advisory.

## Numerical discipline

Copy numerical values exactly from the supplied evidence.

Do not:
- calculate served traffic
- calculate blocked traffic
- calculate remaining capacity
- calculate utilization
- calculate differences between policies
- calculate percentages from ratios
- calculate ratios from percentages
- sum traffic classes
- round values differently
- infer per-service blocking
- infer risk probabilities
- introduce traffic values unless they are explicitly part of the policy-comparison evidence

If the evidence provides:
- SAA blocking = 5.27%
- MBA blocking = 5.27%

you may say:
"SAA and MBA have equal blocking of 5.27%."

You must NOT say:
"SAA has lower blocking than MBA."

## Metric meaning

Do not confuse:
- blocking percentage
- Failure-prone risk
- offered traffic
- served traffic
- provisioned capacity
- reconfiguration count

A blocking value such as 0.91% is a blocking value.
It is not an SLA Failure-prone risk.

A reconfiguration count is not a blocking value.

## Balanced recommendation

The balanced recommendation comes directly from the deterministic policy engine.

Do not invent your own reason for selecting a policy.

Use only recommendation rationale explicitly present in the evidence.

If SAA is recommended:
- do not claim it is recommended because it has the lowest blocking unless the evidence explicitly shows that
- do not claim it serves more traffic unless that comparison is explicitly supplied
- do not claim it is universally superior

If MBA is recommended:
- do not reinterpret that recommendation as SAA
- report MBA as the deterministic balanced recommendation for that timestamp

## Equality and ties

When two or more policies have the same supplied metric value, state that they are equal or tied for that metric.

Never describe equal values as:
- lower
- higher
- better
- worse

unless another supplied deterministic metric differentiates them.

Examples:

Correct:
"MBA and SAA both have 5.27% blocking."

Incorrect:
"SAA has lower blocking than MBA at 5.27%."

## Policy comparison scope

For a balanced policy-comparison query, focus on:
- recommendation
- blocking
- reconfiguration
- SC assignment if useful

Do not add:
- SLA state
- Failure-prone risk
- traffic forecast
- capacity
- congestion interpretation
- generic monitoring advice
- corrective action
- physical-layer reasoning

unless those are explicitly part of the comparison evidence and required to answer the operator's question.

## Advisory wording

Preferred wording:

"At 21:15, the balanced objective recommends SAA. SAA has 5.27% blocking and 0 SC reconfigurations. MBA has the same blocking value at this interval, while the balanced objective selects SAA."

If only the recommended-policy metrics are supplied:

"At 21:15, the balanced objective recommends SAA, with 5.27% blocking and 0 SC reconfigurations."

Do not add explanations that are absent from deterministic evidence.

## Style

Use one short paragraph.

Do not:
- produce a large table
- repeat every internal KPI
- expose tool names
- mention model implementation details
- recommend monitoring or configuration actions

Stop once the policy comparison has been explained.
## Strict evidence boundary for generation

Use only the operator-facing fields present in the supplied policy-comparison evidence.
Do not introduce offered traffic, served traffic, SLA probability, capacity, or any other
number that is not explicitly present in the shaped comparison evidence. If a metric is
not supplied, omit it rather than estimating or reconstructing it.
