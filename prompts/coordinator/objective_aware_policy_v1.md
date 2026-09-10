# Objective-aware policy routing v1

Use `compare_policies_at_time` when the operator expresses an operational objective and asks which policy should be preferred.

The operator does not need to use formal objective names.

Extract:
- timestamp
- objective

Do not interpret an operational objective as an SC allocation constraint.

## Minimum blocking objective

Map these meanings to:

objective = `min_blocking`

Examples:
- "Minimize blocking."
- "Which policy gives the lowest blocking?"
- "Reduce blocked demand."
- "Serve as much demand as possible."
- "I care only about serving the maximum amount of traffic."
- "Reduce blocking rather than optimizing stability."

Use:
`compare_policies_at_time`

Do not use constrained allocation.

## Minimum reconfiguration / stability objective

Map these meanings to:

objective = `min_reconfiguration`

Examples:
- "Use the most stable policy."
- "Which policy causes the fewest reconfigurations?"
- "Keep controller churn to a minimum."
- "Minimize controller churn."
- "Avoid unnecessary reconfiguration."
- "Avoid unnecessary SC changes."
- "Minimize control-plane changes."
- "Prioritize stability."
- "I care about stability above everything else."
- "Avoid reconfiguration above everything else."

Use:
`compare_policies_at_time`

Important:

"churn" means policy/SC reconfiguration overhead.

It is NOT an SC-count constraint.

The words:
- churn
- stability
- reconfiguration
- changes

do not imply constrained allocation unless the operator also gives an explicit SC-count constraint.

Example:

"At 16:20, keep controller churn to a minimum."
→ `compare_policies_at_time`
→ time = 16:20
→ objective = min_reconfiguration

NOT:
→ `analyze_constrained_allocation`

## SLA/service-priority objective

When the operator explicitly prioritizes strict SLA/service ordering, use the configured SLA-priority objective supported by the policy engine.

Examples:
- "Prioritize SLA service order."
- "Use strict service priority."
- "Preserve service-class priority."

Use:
`compare_policies_at_time`

Extract the corresponding configured objective exactly as supported by the runtime.

Do not invent an objective identifier.

## Balanced objective

Map these meanings to:

objective = `balanced`

Examples:
- "Which policy is preferable?"
- "Give me the best compromise."
- "Which policy makes most sense overall?"
- "Balance blocking and stability."

## Objective versus constraint

An objective describes WHAT the operator wants to optimize.

Examples:
- minimize blocking
- minimize churn
- maximize stability
- preserve SLA priority

A constraint specifies a concrete SC allocation requirement.

Examples:
- "Keep RAN on 2 SCs."
- "Reserve one SC for Enterprise."
- "Give PON two subcarriers."

Only use constrained allocation when a concrete allocation constraint is present.

Examples:

"Keep controller churn to a minimum."
→ objective
→ policy comparison

"Keep RAN on 2 subcarriers."
→ constraint
→ constrained allocation

"Minimize reconfiguration."
→ objective
→ policy comparison

"Fix PON to 2 SCs."
→ constraint
→ constrained allocation

## Routing priority

When the request contains:
- an optimization preference but no explicit SC count
→ policy comparison

When the request contains:
- a specific service + explicit SC count
→ constrained allocation

Never create an empty constrained-allocation request from an optimization objective.

## Minimum-blocking semantics

Map all of the following to:

objective = `min_blocking`

- minimize blocking
- lowest blocking
- reduce blocking
- reduce blocked demand
- serve as much demand as possible
- serve the most demand
- maximize served demand
- maximize served traffic
- prioritize serving demand

## Minimum-reconfiguration semantics

Map all of the following to:

objective = `min_reconfiguration`

- minimize reconfiguration
- minimum reconfiguration
- fewest reconfigurations
- avoid unnecessary reconfiguration
- minimize churn
- minimum churn
- controller churn
- keep controller churn to a minimum
- most stable
- maximize stability

These are optimization objectives, not allocation constraints.

Do not route them to constrained allocation unless the operator also provides an explicit service + SC-count restriction.