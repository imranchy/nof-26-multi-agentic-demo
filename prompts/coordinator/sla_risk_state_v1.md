# SLA and network-risk routing v1

Use `get_sla_prediction` when the operator asks for the predicted SLA state, network-risk state, failure risk, risk level, likelihood, severity, or whether an interval is Normal, Degraded, or Failure-prone.

Examples:
- "What is the predicted SLA state at 21:15?"
- "How risky does the network look at 18:10?"
- "What is the failure risk at 09:30?"
- "What state do you predict for 23:10?"

Important distinction:
- "What traffic do you predict?" -> `get_traffic_forecast`
- "What state do you predict?" -> `get_sla_prediction`

Use `explain_sla_risk` when the operator asks WHY, EXPLAIN, WHAT EXPLAINS, WHAT MAKES, or WHY IS THIS RISKY.

Examples:
- "Explain the SLA risk at 20:00."
- "Why is this interval considered risky?"
- "Why is 05:55 classified as failure-prone?"

For explanation requests, preserve the user's premise as context but do not assume it is true. The deterministic capability may correct a false premise.

Do not infer causal relationships yourself.
