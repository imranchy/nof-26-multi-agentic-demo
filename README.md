# NoF 2026 Multi-Agent Digital Twin Demo

Local demonstrator for semantic operator interaction with predictive traffic/SLA state and deterministic PSC subcarrier-allocation policies in a coherent P2MP metro-access network.

## v1 scope

The application combines the frozen prediction models already shipped with the original repository, deterministic PCA/MBA/SAA policy replay, operator SC constraints, temporal analysis, Mistral semantic orchestration, conversational memory, and deterministic grounding guardrails.

Physical-layer analysis, GNPy, RAG, and physical network actuation are intentionally out of scope until calibrated physical-layer parameters and authoritative operational documents are available.

## Operator-facing design

Operators ask natural questions such as:

- `What traffic do you expect at 21:15?`
- `What is the predicted SLA state at 21:15?`
- `What is happening on the network at 21:15?`
- `Which allocation policy would you use at 21:15?`
- `Minimize blocking at 21:15.`
- `What happens if we use PCA instead?`
- `Keep RAN on 2 subcarriers and allocate the remaining two.`
- `Was 18:10 healthier than 21:15?`
- `Summarize the network from 18:00 to 22:00.`
- follow-up: `What about an hour later?`

Normal operator answers do not require or expose ML implementation names. The UI reports **predicted SLA state + Failure-prone risk** rather than a separate classifier-confidence score.

## Architecture

The demo remains fully local. Mistral runs through Ollama and owns multilingual language understanding, conversational context interpretation, native function selection, structured function arguments, and evidence explanation. Python remains the source of truth for state transitions and network computation.

1. The local Mistral context coordinator interprets English, Italian, Portuguese, or code-switched requests and emits only a schema-constrained context relation/inheritance contract.
2. The same local Mistral model receives the actual registered function schemas through Ollama native tool calling and selects exactly one function plus explicit arguments.
3. The selected function identifies the specialist domain (traffic, SLA, policy, network analysis, or scope).
4. Python applies explicit > inherited > default precedence, relative-time arithmetic, constraint merging, enum/range validation, and feasibility checks.
5. Deterministic traffic/SLA models and PCA/MBA/SAA policy code execute locally. Policy metadata and optimization objectives are declarative configuration, not generated code.
6. Mistral explains only returned evidence; grounding guardrails retain deterministic fallback behavior.

There is no Python phrase list or regex router for operator intent, follow-up wording, objectives, policies, or SC constraints. The custom specialist `steps` JSON planner has also been removed in favor of the model's native function-calling interface.

```text
Operator (EN / IT / PT)
        ↓
Local Mistral Context Coordinator
structured conversational contract
        ↓
Local Mistral Native Tool Calling
function name + explicit arguments
        ↓
Deterministic Python
state + arithmetic + validation + network execution
        ↓
Mistral grounded explanation
        ↓
Grounding guardrail / fallback
```

### Structured follow-up contract

For conversational turns, Mistral decides whether intent/time/policy/objective/constraints are inherited. Python never interprets the operator's wording. When `intent` is inherited, Python restricts the native function-calling stage to the previously executed function. This prevents a time-only follow-up from silently changing analytical intent while preserving an explicit intent switch such as traffic → SLA.

If Mistral references state that does not exist, Python requests clarification instead of guessing.

See `docs/ARCHITECTURE_LOCAL_HANDOFF.md` and `UPGRADE_NATIVE_MISTRAL_TOOL_CALLING.md`.

## Prompt versioning

NoF v1 keeps prompts outside application code:

- `prompts/coordinator/*.md`
- `prompts/explainer/*.md`
- `prompts/operator_style_v1.md`
- `config/prompts.yaml`

This allows prompt changes to be evaluated independently of the model and network logic. The coordinator prompt is versioned as `v3-local-handoff`; explainer/operator-style prompts remain independently versioned.

## Failure-prone risk

The Failure-prone risk shown in the dashboard is the probability assigned to the simulator-derived `failure_prone` SLA state by the frozen SLA-state surrogate. Training labels are derived from simulator blocking ratio; the frozen threshold and model limitations are recorded in `models/sla_random_forest.metadata.json`.

See `docs/RISK_SCORE.md` for the exact interpretation. It is not a physical-layer fault probability and is not presented as generic model confidence.

## Windows setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Ollama must be installed and the local model available:

```powershell
ollama pull mistral:7b
```

Or use:

```powershell
.\setup_windows.bat
```

Do not run `train_models.bat` unless you intentionally want to regenerate the original frozen models.

## Deterministic validation

Before testing Mistral:

```powershell
python -m pytest -q
python -m tests.llm.validate_gold
```

`validate_demo.bat` runs the deterministic tests, validates the v1 gold query set, rebuilds ML/policy validation artifacts, and verifies the local installation.

## Mistral evaluation without running the app

The benchmark is under `tests/llm/`; Streamlit does not need to be running.

### v1 operator benchmark

`tests/llm/query_sets/operator_10_categories_v1.json`

- 10 categories
- 10 natural-language variants per category
- 100 queries total

Recommended workflow:

```powershell
python -m tests.llm.validate_gold
python -m tests.llm.evaluate --category traffic_prediction
python -m tests.llm.evaluate --category sla_risk_state
# ...continue category by category...
python -m tests.llm.evaluate --all
```

Windows shortcuts:

```powershell
.\test_llm_category.bat traffic_prediction
.\test_llm_all.bat
.\test_llm_adversarial.bat
```

Results are written to:

`tests/llm/results/v1/`

The application does **not** display benchmark scores. These files are intended for analysis and poster figures/tables.

### Adversarial/hallucination tests

A separate 20-query set tests out-of-domain routing, physical-layer scope, false premises, instruction attempts to invent values, and grounded execution:

```powershell
python -m tests.llm.evaluate_adversarial
```

## Future fine-tuning

No fine-tuning is used in v1. If Mistral is fine-tuned later, preserve the base model and train a separate LoRA/QLoRA adapter on a **different training set**. Do not train on the 100-query v1 benchmark; it should remain held out for before/after comparison.

See `tests/llm/future_training/README.md`.

## Run the application

```powershell
.\launch_demo.bat
```

The UI is a single operator page with:

- active simulated policy / SC configuration
- day-ahead traffic forecast
- Failure-prone risk timeline
- free-form operator assistant
- optional technical trace (off by default)

## Repository map

```text
app/
  agents/              local context coordinator, native tool catalog/caller, explainer, guardrails
  policy_engine/       deterministic PCA/MBA/SAA and metrics
  semantic/            deterministic semantic normalization/safety
  tools/               operator analytical capabilities
  runtime.py           orchestration/memory
  ui.py                Streamlit application

config/
  network.yaml
  sla.yaml
  recommendation.yaml
  operator_policy.yaml
  model.yaml
  prompts.yaml

policies/
  pca.yaml
  mba.yaml
  saa.yaml

prompts/
  coordinator/          routing/context modules
  explainer/            category-grounded explanation modules
  operator_style_v1.md

tests/
  deterministic pytest suite
  llm/
    query_sets/
    results/
    future_training/

validation/
  results/              ML and deterministic policy validation artifacts
```

For detailed evaluation methodology see `docs/EVALUATION_V1.md`; for architecture see `docs/ARCHITECTURE_V1.md`.

## Multilingual semantic coordinator

The coordinator now treats natural-language understanding as an LLM concern and
keeps deterministic Python focused on validation, state transitions, temporal
arithmetic, constraint merging, and network execution. Operator requests may be
written in English, Italian, Portuguese, or code-switch between those languages
and networking terminology. Mistral maps them to the same canonical structured
contract before execution.

The runtime no longer uses Python phrase lists or regex-based operator intent,
objective, follow-up, policy, or SC-constraint parsing. Relative time is emitted
as a structured minute offset and applied deterministically in Python.

Run the multilingual conversational-context benchmark with:

```bash
python tests/llm/evaluate.py --query-set operator_multilingual_context_v1.json --all
```
