# NoF 2026 local multilingual agent-handoff architecture

## Boundary

The demonstrator keeps the entire operator interaction path local. Ollama hosts the
Mistral model; no managed Mistral Agents API, cloud conversation service, web search,
or connector is required for the conference demo.

Mistral owns linguistic decisions:

- multilingual semantic interpretation (English, Italian, Portuguese, code-switching)
- standalone vs follow-up interpretation
- inheritance eligibility
- relative-time offset extraction
- specialist-agent handoff selection
- bounded specialist capability/tool selection
- operator-facing explanation

Python owns deterministic decisions:

- explicit > inherited > default precedence
- clock arithmetic from structured minute offsets
- constraint accumulation and explicit override
- enum/range validation
- SC feasibility and allocation mathematics
- traffic/SLA model execution
- PCA/MBA/SAA execution
- evidence grounding and deterministic fallback

## Local handoff path

```text
Operator query
    ↓
CoordinatorAgent (local Mistral / Ollama)
    ├─ ContextInterpretation
    └─ specialist handoff list
            ↓
LocalSpecialistAgent (same local Mistral / Ollama)
    └─ schema-bounded capability call(s)
            ↓
ConversationStateManager + SemanticResolver
    └─ deterministic state application and value validation
            ↓
OperatorTools / policy engine / frozen predictors
            ↓
ExplanationAgent + grounding guardrail
            ↓
Operator response
```

## Specialist boundaries

- `traffic_agent`: `get_traffic_forecast`
- `sla_agent`: `get_sla_prediction`, `explain_sla_risk`
- `policy_agent`: `compare_policies_at_time`, `simulate_policy_at_time`, `analyze_constrained_allocation`
- `network_analysis_agent`: `get_network_state_at_time`, `compare_network_states`, `find_risk_intervals`, `summarize_time_range`
- `scope_agent`: `decline_physical_layer`, `decline_out_of_scope`

A specialist response is rejected if it attempts to call a capability outside its
registered scope. This keeps local agent handoffs observable and bounded without
hard-coding natural-language routing rules in Python.

## Conversation state

Mistral receives compact structured execution memory and recent structured turns for
linguistic continuity. Python remains authoritative for operational state. Generated
assistant prose is not used as network state.

Typical retained fields include:

- `last_time`
- `last_tool`
- `last_agent`
- `last_policy`
- `recommended_policy`
- `last_objective`
- `last_constraints_raw`
- comparison timestamps
- last deterministic evidence

## Multilingual evaluation

The original English benchmark remains unchanged. A separate Italian/Portuguese
conversational-context suite validates equivalent semantic behavior across languages:

`tests/llm/query_sets/operator_multilingual_context_v1.json`

The benchmark records both the raw specialist-proposed tool sequence and final
executed sequence so local-agent routing errors remain visible.
