# NoF 2026 local multilingual native-tool architecture

## Boundary

The demonstrator keeps the operator interaction path local. Ollama hosts Mistral; no managed Mistral Agents API, cloud conversation service, web search, connector, or server-side code interpreter is required.

Mistral owns semantic decisions:

- multilingual interpretation (English, Italian, Portuguese, code-switching)
- standalone vs follow-up interpretation
- inheritance eligibility
- relative-time offset extraction
- native function/tool selection
- explicit structured function arguments
- operator-facing explanation

Python owns deterministic decisions:

- explicit > inherited > default precedence
- clock arithmetic from structured offsets
- constraint accumulation and explicit override
- enum/range validation
- SC feasibility and allocation mathematics
- traffic/SLA model execution
- PCA/MBA/SAA policy execution
- evidence grounding and deterministic fallback

## Local execution path

```text
Operator query
    ↓
Context Coordinator (local Mistral / structured output)
    └─ ContextInterpretation only
            ↓
Mistral native function calling through Ollama /api/chat
    └─ exactly one registered local function + explicit arguments
            ↓
Tool ownership identifies specialist domain
    ├─ traffic_agent
    ├─ sla_agent
    ├─ policy_agent
    ├─ network_analysis_agent
    └─ scope_agent
            ↓
ConversationStateManager + SemanticResolver
    └─ deterministic inheritance, arithmetic and value validation
            ↓
OperatorTools / policy engine / frozen predictors
            ↓
ExplanationAgent + grounding guardrail
            ↓
Operator response
```

The previous custom specialist `steps` JSON planner has been removed. Mistral now uses the model's native tool-call interface. Python executes the named function locally; Mistral never executes or mutates network state directly.

## Tool boundaries

- `get_traffic_forecast`: direct traffic prediction
- `get_sla_prediction`: direct SLA state/risk prediction
- `explain_sla_risk`: explanation/correction of an SLA claim
- `get_network_state_at_time`: complete one-time snapshot
- `compare_policies_at_time`: policy comparison / objective-aware recommendation
- `simulate_policy_at_time`: one named-policy counterfactual
- `analyze_constrained_allocation`: explicit hard SC-count constraints
- `compare_network_states`: explicit two-time comparison
- `find_risk_intervals`: ranked top-k discovery
- `summarize_time_range`: continuous time-window summary
- scope-decline tools: unsupported requests

Tool descriptions deliberately distinguish optimization objectives from hard SC-count constraints and named-policy counterfactuals from complete network snapshots.

## Conversation state

Mistral receives compact structured execution memory and recent structured turns for linguistic continuity. Python remains authoritative for operational state. Generated assistant prose is not used as network state.

When Mistral marks `intent` as inherited, Python exposes only the previously executed native function on that follow-up. This enforces conversational continuity without matching any operator phrase.

If referenced state is missing, Python asks for clarification rather than inventing a timestamp, policy, objective, or constraint.

## Policy configuration

Policy definitions remain deterministic and reproducible. Metadata lives in `policies/*.yaml`; optimization objectives live in `config/recommendation.yaml`. Mistral may choose a configured policy/objective through structured function arguments, but it does not generate authoritative policy code at runtime.

This deliberately avoids arbitrary LLM-generated Python in the network control path while still removing language-routing code.

## Multilingual evaluation

The original English benchmark remains unchanged. A separate Italian/Portuguese conversational-context suite validates equivalent semantic behavior across languages:

`tests/llm/query_sets/operator_multilingual_context_v1.json`

The evaluator records the raw native Mistral tool call and the final executed call so routing/argument errors remain visible.
