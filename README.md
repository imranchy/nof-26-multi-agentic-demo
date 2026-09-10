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

Mistral is the semantic interface, not the numerical source of truth.

1. Traffic/SLA prediction capabilities provide the predicted state.
2. The deterministic PSC engine executes PCA, MBA, and SAA.
3. Mistral interprets natural language, extracts timestamps/objectives/constraints, and produces a bounded tool plan.
4. Deterministic argument normalization catches explicit routing mistakes.
5. Mistral explains the returned evidence.
6. Grounding guardrails reject unsupported numeric, categorical, causal, physical-layer, or implementation-detail claims and fall back to deterministic text.

Policy algorithms remain Python source-of-truth implementations. YAML files contain declarative policy and operator-policy metadata.

## Prompt versioning

NoF v1 keeps prompts outside application code:

- `prompts/coordinator_v1.md`
- `prompts/explainer_v1.md`
- `prompts/operator_style_v1.md`
- `config/prompts.yaml`

This allows prompt changes to be evaluated independently of the model and network logic. All v1 prompt versions are `v1`.

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
  agents/              Mistral coordinator/explainer + guardrails + prediction wrappers
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
  coordinator_v1.md
  explainer_v1.md
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
