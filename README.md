# NoF 2026 Multi-Agent Digital Twin Demo

Fully local operator-facing demonstrator for predictive traffic/SLA analysis and deterministic PSC subcarrier-allocation policies in a coherent P2MP metro-access network.

## Architecture

The runtime deliberately has one language-routing path:

```text
Operator (English / Italian / Portuguese)
        |
        v
Local Mistral 7B through Ollama /api/chat
conversation + compact authoritative state + function schemas
        |
        v
Native tool call: function name + structured arguments
        |
        v
Deterministic Python
validation + time arithmetic + state + ML/network/policy execution
        |
        v
Mistral grounded explanation
        |
        v
Grounding guardrail / deterministic fallback
```

There is no coordinator, deterministic intent router, phrase list, regex router, or Python agent-handoff decision in the operator path. Mistral chooses the supported function directly. Python remains authoritative only for deterministic computation, validation, state, feasibility and safety.

## Supported operator capabilities

- traffic/load forecast at one timestamp
- SLA state / Failure-prone risk
- SLA-risk explanation
- complete network-state snapshot
- policy comparison and objective-aware selection
- named-policy counterfactual simulation
- explicit SC-allocation constraints
- two-time network comparison
- ranked day-ahead risk/load/blocking/reconfiguration intervals
- continuous time-range summary
- conversational follow-ups using compact stored state

Policy IDs and objective vocabularies are configuration-driven. PCA/MBA/SAA execution, subcarrier feasibility, time arithmetic, ML inference and policy scoring remain deterministic Python operations.

## Local setup

Recommended on Windows:

```powershell
.\setup_windows.bat
```

Or manually:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull mistral:7b
```

The `.venv/` directory is intentionally ignored by Git and should be created locally.

## Verify the repository

```powershell
python -m pytest -q
python -m tests.llm.validate_gold
```

## Live single-query smoke test

```powershell
python -c "from app.runtime import MultiAgentRuntime; import pprint; r=MultiAgentRuntime(); x=r.ask('What traffic do you expect at 21:15?'); print('TOOL:', x.plan.tool_name); print('ARGS:', x.plan.arguments); pprint.pp(x.routing_audit)"
```

Expected tool:

```text
get_traffic_forecast
```

## LLM evaluation

50-query development suite:

```powershell
python tests\llm\evaluate.py --query-set operator_manual_5x10_v1.json --all
```

100-query held-out suite:

```powershell
python tests\llm\evaluate.py --query-set operator_10_categories_v1.json --all
```

Multilingual conversational suite:

```powershell
python tests\llm\evaluate.py --query-set operator_multilingual_context_v1.json --all
```

Generated benchmark results are written under `tests/llm/results/` and are ignored by Git.

## Run the demo

```powershell
python launcher.py
```

or:

```powershell
streamlit run app/ui.py
```

The repository keeps `demo queries.docx` as the live demonstration query sheet and `Imran_NoF_26.pptx` as the presentation deck.

## Main repository layout

```text
app/
  agents/
    specialist.py      direct Mistral/Ollama native tool router
    tool_catalog.py    function schemas exposed to Mistral
    explanation.py     grounded operator-facing response generation
    guardrail.py       evidence-grounding validation
  policy_engine/       deterministic PCA/MBA/SAA execution and metrics
  semantic/            structured value normalization/validation only
  tools/               deterministic operator analytical functions
  runtime.py           direct tool-call orchestration and conversation state
  state_manager.py     compact authoritative state + time arithmetic
  ui.py                Streamlit demo UI

config/                 network/model/prompt/objective configuration
policies/               declarative PCA/MBA/SAA metadata
prompts/                direct tool-router + grounded explainer prompts
tests/                  deterministic tests and LLM benchmarks
models/                  frozen traffic/SLA models
validation/              deterministic validation artifacts
```

Physical-layer analysis, GNPy, live network actuation and RAG remain intentionally out of scope for this demonstrator.
