# Conversational context routing v1

Resolve conversational references using the supplied context, but always
identify the current operator intent before inheriting the previous tool.

## Current intent overrides previous tool

A contextual reference such as:

- that time
- same time
- then
- an hour later
- next interval

may supply a missing timestamp.

It does not force reuse of the previous analytical capability.

Examples:

Operator:
"What traffic do you expect at 08:15?"

Follow-up:
"At that time, what is the SLA risk?"

-> use `get_sla_prediction`
-> time = 08:15

Do NOT reuse `get_traffic_forecast`.

Operator:
"Show me the network state at 18:10."

Follow-up:
"What about an hour later?"

-> use `get_network_state_at_time`
-> time = 19:10

Here the follow-up contains no new analytical intent, so preserving the
previous capability is correct.

## Policy references

When the context identifies a recommended or previously simulated policy,
resolve:

- that policy
- the recommended policy
- it
- same policy

only when unambiguous.

If the follow-up asks for performance or outcome, use a policy
counterfactual rather than blindly repeating the previous comparison.

Example:

Operator:
"Compare PCA, MBA and SAA at 20:00 and recommend one."

Follow-up:
"What performance does that policy give?"

-> `simulate_policy_at_time`
-> use the recommended policy
-> time = 20:00

## Explicit policy overrides context

If the current query explicitly names PCA, MBA, or SAA, use that policy even
if another policy was stored in conversation context.

Example:

Operator:
"Which policy would you use at 18:30?"

Follow-up:
"Use PCA instead and show me the outcome."

-> `simulate_policy_at_time`
-> policy = PCA
-> time = 18:30

## Constraint continuation

When a constrained-allocation follow-up says:

- also
- in addition
- as well
- and keep
- and give

merge the new explicit constraint with the existing constraint context.

Do not discard previously stated constraints unless the operator explicitly
replaces them.

Example:

Operator:
"Keep RAN on 2 subcarriers at 19:00."

Follow-up:
"Also keep PON on 1 SC."

-> retain RAN = 2
-> add PON = 1
-> retain time = 19:00

## Minimum-tool rule

Use the current query's intent and only inherit missing arguments from context.

Do not reuse the previous tool merely because the query contains a contextual
time reference.