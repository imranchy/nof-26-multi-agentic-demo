# Local specialist handoffs v1

Select the minimum specialist set according to the analytical meaning of the request.

- `traffic_agent`: offered-traffic prediction at a timestamp.
- `sla_agent`: SLA state / Failure-prone risk, including correcting a claimed SLA state.
- `policy_agent`: policy comparison, objective-aware policy choice, named-policy counterfactuals, and explicit SC-allocation constraints.
- `network_analysis_agent`: complete network state, comparison between timestamps, ranked high-risk/high-load/high-blocking/high-reconfiguration intervals, and continuous time-range summaries.
- `scope_agent`: unsupported physical-layer analysis or generic non-network requests.

A secondary qualifier such as an objective, policy name, metric, or timestamp does not
replace the primary analytical intent. Use more than one handoff only when the
operator explicitly asks for distinct analytical outputs requiring different
specialists.

For a conversational follow-up with no new analytical intent, use structured memory
and history to select the specialist associated with the inherited intent.

For a follow-up that changes intent while referring to prior time, policy, objective,
constraints, or other context, select the new specialist and let the context contract
identify what may be inherited.

## Inherited analytical intent

When the current utterance is a follow-up and does not explicitly request a new
analytical operation, preserve the analytical intent of the immediately preceding
operator request.

A change in timestamp, policy argument, objective, or constraint does not by itself
change the analytical intent.

Examples:

- previous traffic prediction + later-time follow-up
  -> remain a traffic prediction handled by `traffic_agent`

- previous SLA prediction + later-time follow-up
  -> remain an SLA prediction handled by `sla_agent`

- previous complete network-state request + later-time follow-up
  -> remain a complete network-state request handled by `network_analysis_agent`

- previous policy analysis + changed policy/objective
  -> remain policy analysis handled by `policy_agent`

Do not broaden a specific inherited analytical intent into a more general capability.

In particular, `network_analysis_agent` is not a general fallback merely because
complete network state contains traffic, SLA, policy, and allocation information.

A relative-time follow-up does not imply temporal comparison. Select comparison only
when the operator explicitly requests comparison, difference, change, delta, or
another analysis involving both states.

## Missing relative-time context

A relative-time request may inherit time only when a valid previous timestamp exists
in structured conversation state.

If a valid previous timestamp exists, preserve the previous analytical intent and
apply the structured relative-time offset.

If no previous timestamp exists, do not invent a reference timestamp and do not choose
an arbitrary network interval. The request requires clarification of the reference
time.

Always choose the minimum specialist set required to satisfy the operator request.

## Inherited analytical intent

When the current utterance is a follow-up and does not explicitly request a new
analytical operation, preserve the analytical intent of the immediately preceding
operator request.

A change in timestamp, policy argument, objective, or constraint does not by itself
change the analytical intent.

Examples:

- previous traffic prediction + later-time follow-up
  -> remain a traffic prediction handled by `traffic_agent`

- previous SLA prediction + later-time follow-up
  -> remain an SLA prediction handled by `sla_agent`

- previous complete network-state request + later-time follow-up
  -> remain a complete network-state request handled by `network_analysis_agent`

- previous policy analysis + a changed policy/objective
  -> remain a policy-analysis request handled by `policy_agent`

Do not broaden a specific inherited analytical intent into a more general capability.

In particular, `network_analysis_agent` is not a general fallback merely because a
complete network-state result contains traffic, SLA, policy, and allocation information.

A relative-time follow-up does not imply temporal comparison. Select comparison only
when the operator explicitly requests a comparison, difference, change, delta, or
other analysis involving both states.

Always choose the minimum specialist set required to satisfy the current operator request.

## Follow-up intent preservation

When a follow-up changes only a missing argument such as time, policy, objective, or
constraint, preserve the previous analytical intent unless the current utterance
explicitly requests a different analytical operation.

A relative temporal reference by itself does NOT imply temporal comparison.

For example, if the previous request asks for a network-state snapshot and the
follow-up asks about a later time, keep the network-state intent and hand off only
to `network_analysis_agent`.

Do not reinterpret a later-time follow-up as a cross-time comparison unless the
operator explicitly asks to compare, contrast, show the change/difference, or
otherwise requests both states as analytical outputs.

Likewise, a follow-up that adds a constraint does not authorize additional network
state, comparison, forecast, or SLA analysis unless those outputs are explicitly
requested.

Always choose the smallest specialist set that can satisfy the current operator
request.
