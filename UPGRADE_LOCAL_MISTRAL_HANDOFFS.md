# Local Mistral handoff upgrade

This upgrade keeps the NoF demo local through Ollama while moving linguistic decisions
out of Python.

## Main changes

- Coordinator now emits multilingual conversational context plus specialist handoffs.
- Added bounded local specialists with schema-constrained capability sets.
- The same local Mistral model is used for coordinator and specialist stages.
- Python no longer parses operator wording for intent/follow-up/objective/policy/SC constraints.
- Relative-time language is converted by Mistral to a minute offset; Python performs the clock arithmetic.
- Structured Python memory remains authoritative for operational state.
- Added Italian and Portuguese conversational-context evaluation cases.
- Existing English 100-query gold benchmark is unchanged.

## Verification completed in the packaged repository

```text
52 pytest tests passed
100-query gold benchmark schema validated
static operator-language parsing audit: no phrase router found in runtime/state/resolver/coordinator/specialist path
```

A live LLM benchmark was not run while packaging because it requires your local Ollama
server and installed Mistral model.

## Recommended local evaluation order

```powershell
python -m pytest -q
python -m tests.llm.validate_gold
python tests\llm\evaluate.py --query-set operator_manual_5x10_v1.json --category conversational_context
python tests\llm\evaluate.py --query-set operator_multilingual_context_v1.json --all
python tests\llm\evaluate.py --query-set operator_manual_5x10_v1.json --all
```
