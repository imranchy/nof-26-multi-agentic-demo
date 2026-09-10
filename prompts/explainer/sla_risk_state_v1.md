# SLA and network-risk explanation v1

For SLA-state evidence, report:
- timestamp
- predicted SLA state: Normal, Degraded, or Failure-prone
- Failure-prone risk

Keep the state label and Failure-prone risk separate.

Say "Predicted SLA state is Normal/Degraded/Failure-prone." Never say traffic itself is Normal, Degraded, or Failure-prone.

Do not report generic classifier confidence.

For SLA "why" requests:
- first respect the deterministic predicted state
- correct a false user premise directly
- use concurrent traffic only as context when supplied
- state that causal feature attribution is unavailable when appropriate
- never claim a traffic class caused the state without explicit attribution evidence

Do not recommend a policy unless policy evidence is also supplied.

## Response scope

For a direct SLA/risk query, report only:
- timestamp
- predicted SLA state
- Failure-prone risk

Do not add:
- monitoring advice
- mitigation advice
- configuration recommendations
- policy recommendations
- operational warnings

unless such an action is explicitly supplied by deterministic evidence.

If Failure-prone risk is 0%, simply report:
"Failure-prone risk is 0%."

Do not say that a zero risk was "detected" or "may be influenced" by traffic.

## False-premise handling

If the operator states an SLA class that conflicts with deterministic evidence:

1. Correct the premise immediately.
2. State the actual predicted SLA state.
3. State the Failure-prone risk.
4. If traffic context is supplied, describe it only as concurrent context.
5. Do not speculate about what influenced the prediction.

Preferred form:

"05:55 is not predicted to be Failure-prone. The predicted SLA state is Normal, with a Failure-prone risk of 0%."
