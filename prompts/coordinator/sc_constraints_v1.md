# SC constraints routing v1

Use `analyze_constrained_allocation` whenever the operator imposes an explicit
subcarrier-allocation restriction and asks the system to evaluate, complete, or
optimize the remaining allocation.

An explicit SC constraint is the primary intent. A policy objective such as
minimum blocking, stability, or balanced operation modifies the constrained
allocation; it does not replace it with policy comparison.

## Core routing rule

Route to `analyze_constrained_allocation` when the request contains at least one
explicit service-to-SC restriction, including:

- reserve N SCs for SERVICE
- keep SERVICE on N SCs
- give SERVICE N SCs
- allocate N SCs to SERVICE
- put SERVICE on N SCs
- SERVICE must have N SCs
- exactly N SCs for SERVICE
- one SC for each service
- N subcarriers for SERVICE

SERVICE may be:

- Enterprise
- RAN
- PON

SC and subcarrier mean the same thing.

## Constraint precedence

When an explicit SC allocation constraint is present, use
`analyze_constrained_allocation` even if the request also contains:

- optimize the rest
- allocate the remaining SCs
- minimum blocking
- minimize blocking
- stability
- favor stability
- minimum reconfiguration
- balanced objective

These phrases specify how the unconstrained remainder should be optimized.
They do not turn the request into `compare_policies_at_time`.

Examples:

"Keep RAN on 2 subcarriers at 21:15 and allocate the remaining two."

-> `analyze_constrained_allocation`
-> time = 21:15
-> ran_subcarriers = 2

"At 16:20 reserve one SC for PON and minimize blocking with the rest."

-> `analyze_constrained_allocation`
-> time = 16:20
-> pon_subcarriers = 1
-> objective = min_blocking

"Keep Enterprise on 1 SC at 23:10 and favor stability for the remaining capacity."

-> `analyze_constrained_allocation`
-> time = 23:10
-> enterprise_subcarriers = 1
-> objective = min_reconfiguration

"At 05:55, keep RAN on 2 subcarriers and use a balanced objective for the rest."

-> `analyze_constrained_allocation`
-> time = 05:55
-> ran_subcarriers = 2
-> objective = balanced

## Single-constraint examples

"Reserve 2 SCs for RAN at 18:10."

-> `analyze_constrained_allocation`
-> time = 18:10
-> ran_subcarriers = 2

"Give Enterprise 1 subcarrier at 09:30 and optimize the rest."

-> `analyze_constrained_allocation`
-> time = 09:30
-> enterprise_subcarriers = 1

"At 14:05 keep PON on 2 SCs."

-> `analyze_constrained_allocation`
-> time = 14:05
-> pon_subcarriers = 2

## Multiple constraints

Extract every explicit service constraint from the same request.

"Allocate exactly 2 subcarriers to RAN and 1 to Enterprise at 07:45."

-> `analyze_constrained_allocation`
-> time = 07:45
-> ran_subcarriers = 2
-> enterprise_subcarriers = 1

"At 12:35 put RAN on 2 SCs and PON on 1 SC."

-> `analyze_constrained_allocation`
-> time = 12:35
-> ran_subcarriers = 2
-> pon_subcarriers = 1

"Reserve 1 subcarrier for each service at 20:00."

-> `analyze_constrained_allocation`
-> time = 20:00
-> enterprise_subcarriers = 1
-> ran_subcarriers = 1
-> pon_subcarriers = 1

The phrase "each service" means Enterprise, RAN, and PON.
Do not drop any explicitly stated constraint.

## Objective extraction

When an objective is stated in the constrained request, preserve it as an
argument to `analyze_constrained_allocation`.

Map:

- minimum blocking
- minimize blocking
- minimise blocking
- lowest blocking

-> `min_blocking`

Map:

- stability
- favor stability
- favour stability
- prioritize stability
- prioritise stability
- minimum reconfiguration
- minimum churn
- fewest reconfigurations

-> `min_reconfiguration`

Map:

- balanced
- balanced objective
- best compromise
- trade-off

-> `balanced`

If no objective is explicitly stated, do not invent one in the coordinator
arguments; allow the deterministic capability to use its configured default.

## Constraint versus network state

A constrained allocation request asks:

"What allocation is possible or preferred while respecting this restriction?"

A network-state request asks:

"What is the network currently like?"

Examples:

"Reserve 2 SCs for RAN at 18:10."

-> `analyze_constrained_allocation`

"Show the network state at 18:10."

-> `get_network_state_at_time`

Do not use `get_network_state_at_time` merely because the request contains a
timestamp.

## Constraint versus policy comparison

Do not use `compare_policies_at_time` when the operator explicitly fixes or
reserves SCs for one or more services.

"Minimize blocking at 16:20."

-> `compare_policies_at_time`

"Reserve one SC for PON at 16:20 and minimize blocking with the rest."

-> `analyze_constrained_allocation`

The explicit allocation restriction takes precedence.

## Constraint versus temporal comparison

Do not use `compare_network_states` for a constrained request containing one
timestamp and multiple service constraints.

"At 12:35 put RAN on 2 SCs and PON on 1 SC."

-> `analyze_constrained_allocation`

The numbers 2 and 1 are SC counts, not timestamps to compare.

## Timestamp extraction

Extract the explicit timestamp exactly.

Examples:

"at 21:15" -> 21:15
"at 09:30" -> 09:30

Do not invent a timestamp.

## Tool boundary

Use one `analyze_constrained_allocation` call when it fully answers the
constraint request.

Do not add network-state retrieval, policy comparison, temporal comparison,
traffic forecasting, or SLA prediction merely to make the response more
complete.

Once all explicit constraints, the timestamp, and any explicit objective are
captured, stop.
