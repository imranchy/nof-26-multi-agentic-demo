# NoF 2026 Multi-Agentic Demo

Local demonstrator for **Multi-Agent Digital Twin for SLA Management in Coherent P2MP Metro-Access Networks**.

The application combines an XGBoost traffic forecaster, Random Forest SLA-state classifier, deterministic recovery catalogue, validation guardrails, a schema-constrained Mistral tool-calling coordinator, conversation state, and a Streamlit dashboard. RAG is intentionally excluded because no authoritative operational document corpus is available.

## Agents

1. Coordinator Agent: uses Mistral structured output to select a specialist capability and arguments from the operator's natural-language request.
2. Forecast Agent: runs or loads the day-ahead XGBoost forecast.
3. SLA Agent: predicts Normal, Degraded, and Failure-prone states.
4. Diagnosis Agent: identifies dominant services and interval changes.
5. Recovery Agent: selects an approved advisory action.
6. Guardrail Agent: validates traffic, timestamps, probabilities, and schemas.
7. Operator Response Agent: asks Mistral to express returned tool evidence in concise operator language; deterministic checks reject invented numeric claims, incorrect units, or misleading probability wording.

Mistral performs both tool selection and grounded answer composition. It cannot modify ML predictions or create recovery actions: specialist Python agents execute every tool, and the Guardrail Agent validates the generated answer. Agent Evidence records `selected_tool`, tool arguments, returned evidence, and `source=mistral-tool-call`. The application fails closed if Ollama is unavailable, making LLM use verifiable rather than silently falling back.

## Native tools

- `summarize_day_ahead`
- `find_next_sla_risk`
- `find_highest_risk`
- `find_service_peak`
- `rank_service_intervals`
- `diagnose_highest_risk`
- `recommend_subcarrier_allocation`
- `check_allocation_feasibility`
- `compare_service_loads`
- `get_state_distribution`
- `validate_forecast`
- `decline_out_of_scope`

Tool definitions are the system's capability contract, not a list of hardcoded demo questions. This lets Mistral interpret paraphrases and conversational follow-ups such as “Do the same for PON.” Private chain-of-thought is not displayed; native tool calls and validated evidence provide the auditable execution record.

## Windows quick start

Install standard 64-bit Python 3.12 (recommended) or 3.11 and Ollama first. Do not use the experimental free-threaded Python build. Then double-click:

1. `setup_windows.bat`
2. `train_models.bat`
3. `launch_demo.bat`

The application opens locally in the default browser in a fixed conference configuration: prepared XGBoost forecast data, Mistral native tool selection and answer composition, deterministic specialist execution, and no development controls.

## Equivalent commands

```powershell
cd "nof-26-multi-agentic-demo"
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
ollama pull mistral:7b
python -m scripts.train_forecaster
python -m scripts.train_classifier
python -m scripts.verify_install
python launcher.py
```

Run tests:

```powershell
python -m pytest -q
```

Build the Windows application folder:

```powershell
build_executable.bat
```

The executable is written to `dist\NoF2026MultiAgentDemo\`. Ollama and `mistral:7b` remain separately installed because bundling multi-gigabyte LLM weights inside the executable is unreliable.

## Create the GitHub repository

After testing locally, install GitHub CLI, authenticate with `gh auth login`, and run:

```powershell
git init
git add .
git commit -m "Build NoF 2026 multi-agentic SLA demo"
gh repo create nof-26-multi-agentic-demo --private --source=. --remote=origin --push
```

Change `--private` to `--public` only when the authors are ready to release the data and code.

## Research limitations

- The included data are simulated rather than live telemetry.
- The SLA classifier is a surrogate trained from one allocation scenario day. Its interval-level random split does not demonstrate generalization across unseen days.
- Recovery actions are advisory; the application performs no closed-loop network actuation.
- Prepared mode uses the paper's fixed last-day XGBoost results. Live mode re-executes the saved forecaster for that held-out day.

These limitations are displayed honestly while the demonstration focuses on multi-agent coordination, validation, explanation, and proactive decision support.
