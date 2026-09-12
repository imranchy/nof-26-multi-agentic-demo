# Local Mistral context/handoff stabilization

This repository revision keeps the demo fully local and removes operator-language parsing from Python while hardening conversational context.

## Key changes

- cleaned duplicated coordinator handoff instructions
- preserved local Mistral coordinator + specialist handoffs
- added structured inherited-intent contract enforcement
- restricted a specialist to the previous capability when Mistral explicitly declares `intent` inheritance
- added missing-inherited-state validation (including relative time without a base timestamp)
- retained deterministic relative-time arithmetic and SC-constraint merging
- retained explicit > inherited > default precedence
- kept temperature at 0 for coordinator/specialist/explainer
- added same-language explanation guidance for English/Italian/Portuguese requests
- added regression tests for inherited handoffs, capability locks, and missing context

## Recommended local test order

```powershell
python -m pytest -q
python tests\llm\evaluate.py --query-set operator_manual_5x10_v1.json --category conversational_context
python tests\llm\evaluate.py --query-set operator_multilingual_context_v1.json --all
python tests\llm\evaluate.py --query-set operator_manual_5x10_v1.json --all
python tests\llm\evaluate.py --query-set operator_10_categories_v1.json --all
```

The live Mistral evaluations require the local Ollama service/model and are intentionally not run during offline packaging.
