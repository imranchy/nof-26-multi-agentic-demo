# Policy counterfactual routing v1

Use `simulate_policy_at_time` when the operator asks for the simulated,
hypothetical, counterfactual, or policy-specific performance of one named
allocation policy — PCA, MBA, or SAA — at a timestamp.

This capability answers:

"What would this specific policy produce if it were used?"

Use the minimum single tool required.

## Core routing rule

Route to `simulate_policy_at_time` when:

1. one specific policy is identified or clearly resolved from conversation
   context, and
2. the operator asks what that policy would produce, how it would perform,
   what its outcome would be, or asks to simulate, try, or use it
   hypothetically.

Do not require the literal word "counterfactual".
Determine the meaning of the request.

## Strong counterfactual signals

The following meanings strongly indicate `simulate_policy_at_time` when
they refer to one specific policy:

- what happens if we use POLICY
- what if we use POLICY
- what would POLICY do
- simulate POLICY
- run POLICY
- run a counterfactual with POLICY
- try POLICY
- try POLICY instead
- use POLICY instead
- if we use POLICY
- if we used POLICY
- if the controller used POLICY
- if the controller uses POLICY
- POLICY performance
- performance of POLICY
- POLICY outcome
- outcome of POLICY
- counterfactual POLICY allocation
- show the counterfactual for POLICY
- show POLICY performance
- show the POLICY outcome
- what performance do we get with POLICY
- what does POLICY produce

Examples:

"What happens if we use PCA at 21:15?"

-> `simulate_policy_at_time`
-> time = 21:15
-> policy = PCA

"Simulate MBA at 18:10."

-> `simulate_policy_at_time`
-> time = 18:10
-> policy = MBA

"Show me SAA performance at 09:30."

-> `simulate_policy_at_time`
-> time = 09:30
-> policy = SAA

"What would PCA do at 14:05?"

-> `simulate_policy_at_time`
-> time = 14:05
-> policy = PCA

"Run a counterfactual with MBA at 07:45."

-> `simulate_policy_at_time`
-> time = 07:45
-> policy = MBA

"If we use SAA at 16:20, what performance do we get?"

-> `simulate_policy_at_time`
-> time = 16:20
-> policy = SAA

"Try PCA instead at 23:10."

-> `simulate_policy_at_time`
-> time = 23:10
-> policy = PCA

"Show the MBA outcome at 12:35."

-> `simulate_policy_at_time`
-> time = 12:35
-> policy = MBA

"At 20:00, what if the controller used SAA?"

-> `simulate_policy_at_time`
-> time = 20:00
-> policy = SAA

"Give me the counterfactual PCA allocation at 05:55."

-> `simulate_policy_at_time`
-> time = 05:55
-> policy = PCA

## Counterfactual versus network state

Do not confuse policy simulation with network-state retrieval.

A network-state request asks:

"What is the network state under this policy?"

A policy counterfactual asks:

"What would this policy produce?"

Use `get_network_state_at_time` for an ordinary state, status, condition,
or snapshot request.

Use `simulate_policy_at_time` for policy performance, outcome,
hypothetical behavior, or counterfactual simulation.

Examples:

"Show the network at 20:00 under MBA."

-> `get_network_state_at_time`

"What happens if we use MBA at 20:00?"

-> `simulate_policy_at_time`

"Show the current SAA network state."

-> `get_network_state_at_time`

"Show SAA performance at 09:30."

-> `simulate_policy_at_time`

"What would PCA do at 14:05?"

-> `simulate_policy_at_time`

"Show the MBA outcome at 12:35."

-> `simulate_policy_at_time`

The following meanings strongly favor policy simulation over
network-state retrieval:

- performance
- outcome
- simulate
- counterfactual
- hypothetical
- what if
- what would
- try
- instead

## Counterfactual versus policy comparison

Do not use `compare_policies_at_time` when the operator names one
specific policy and asks what that policy would produce.

Examples:

"Which policy performs best at 20:00?"

-> `compare_policies_at_time`

"Compare PCA, MBA, and SAA at 20:00."

-> `compare_policies_at_time`

"What would PCA do at 20:00?"

-> `simulate_policy_at_time`

"Show MBA performance at 20:00."

-> `simulate_policy_at_time`

A request to evaluate one named policy is not automatically a request
to compare or recommend policies.

## Policy extraction

The policy argument must be exactly one of:

- PCA
- MBA
- SAA

Preserve the policy identifier exactly.

Examples:

"PCA" -> PCA

"MBA" -> MBA

"SAA" -> SAA

Do not translate, expand, rename, or substitute the policy.

If the operator explicitly names a policy, that explicit policy
overrides unrelated policy values from previous conversation context.

## Timestamp extraction

Extract an explicit timestamp exactly as stated.

Examples:

"at 21:15" -> 21:15

"at 09:30" -> 09:30

"At 20:00, what if the controller used SAA?" -> 20:00

If no timestamp is explicitly stated, use valid conversation context
only when the timestamp is unambiguous.

Do not invent a timestamp.

Do not replace an explicit timestamp with one from conversation memory.

## Contextual references

Resolve references such as:

- that policy
- the recommended policy
- that one
- it
- instead

only when conversation context clearly identifies the referenced policy.

Example:

Operator:

"Which policy is preferable at 21:15?"

System recommendation:

SAA

Operator:

"Simulate that policy."

-> `simulate_policy_at_time`
-> policy = SAA
-> time = 21:15

If the reference is ambiguous, do not invent a policy.

## Tool boundary

`simulate_policy_at_time` performs one deterministic counterfactual
policy simulation.

Do not add other analytical tools merely to make the response more
complete.

In particular, a normal policy-counterfactual request does not require:

- `get_traffic_forecast`
- `get_sla_prediction`
- `get_network_state_at_time`
- `compare_policies_at_time`

unless the operator explicitly asks for those additional analyses.

For a request that only asks what one named policy would produce, use:

`simulate_policy_at_time`

and stop.