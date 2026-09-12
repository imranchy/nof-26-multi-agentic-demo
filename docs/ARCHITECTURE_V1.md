# Architecture v1

The demonstrator is fully local: Mistral runs through Ollama and handles natural-language semantics; Python remains authoritative for network state, arithmetic, validation, and execution.

## Runtime path

```text
Operator (English / Italian / Portuguese / code-switched)
        ↓
Local Mistral coordinator
context relation + inheritance contract + specialist handoff
        ↓
Structured-state contract enforcement
(no operator-language parsing)
        ↓
Local Mistral specialist
bounded capability selection + explicit arguments
        ↓
Deterministic Python
precedence + relative-time arithmetic + constraint merge + enum/range checks
        ↓
Traffic/SLA models + deterministic PCA/MBA/SAA/network tools
        ↓
Mistral grounded explanation
        ↓
Grounding guardrail / deterministic fallback
```

## Responsibilities

**Mistral semantic layer**
- multilingual intent understanding
- standalone vs follow-up interpretation
- semantic inheritance declaration (`intent`, `time`, `policy`, `objective`, `constraints`)
- relative-time offset extraction
- specialist handoff selection
- specialist capability selection
- operator-facing explanation

**Deterministic Python layer**
- validate the structured context contract
- enforce inherited-intent continuity once Mistral declares intent inheritance
- reject missing referenced conversational state and request clarification
- explicit > inherited > default precedence
- clock arithmetic from structured offsets
- constraint accumulation/override
- canonical time/policy/objective/metric validation
- feasibility and capacity checks
- deterministic network/policy execution
- grounding checks and safe fallbacks

Python does not use phrase lists, regex intent routing, language-specific follow-up markers, or hard-coded English/Italian/Portuguese semantic mappings.

## Local agent handoffs

The coordinator selects from bounded specialists:

- `traffic_agent`
- `sla_agent`
- `policy_agent`
- `network_analysis_agent`
- `scope_agent`

Each specialist receives only its registered capabilities. When the coordinator declares that analytical intent is inherited, the specialist schema is further restricted to the previously executed capability. This is deterministic enforcement of an LLM-produced semantic contract, not a language heuristic.

## Safety boundary

The LLM may propose meaning and structured arguments, but it cannot mutate application state or perform network actuation. Prediction, policy metrics, temporal arithmetic, SC feasibility, state mutation, and execution remain deterministic.

Physical-layer analysis, GNPy, RAG, web search, managed cloud agents, and network actuation remain out of scope for v1.
