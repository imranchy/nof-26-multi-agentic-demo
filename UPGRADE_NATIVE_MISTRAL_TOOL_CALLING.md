# Native Mistral tool-calling upgrade

This revision replaces the custom specialist JSON-plan stage with Ollama native tool calling using the local `mistral:7b` model.

## What changed

- Context coordinator now interprets conversation state only.
- Native `/api/chat` tool calling selects exactly one analytical function and explicit arguments.
- The selected function maps to the existing specialist domain for traces/UI.
- Python executes the function locally and remains authoritative for arithmetic, state, constraints, validation, models and policy mathematics.
- Tool schemas are centralized in `app/agents/tool_catalog.py`.
- Policy IDs and objective IDs are derived from repository configuration instead of duplicated routing constants.
- Policy/objective descriptions distinguish optimization goals from hard SC-count constraints.
- No arbitrary runtime-generated Python is used for network policies.
- Guardrail and deterministic fallback behavior remain in place.

## Local requirements

Use an Ollama Mistral build with tool support (`mistral:7b` currently maps to Mistral 7B v0.3 in Ollama).

## Recommended validation order

```powershell
python -m pytest -q
python tests\llm\evaluate.py --query-set operator_manual_5x10_v1.json --category conversational_context
python tests\llm\evaluate.py --query-set operator_manual_5x10_v1.json --all
python tests\llm\evaluate.py --query-set operator_gold_10x10_v1.json --all
```
