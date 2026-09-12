# NoF local Mistral evaluation

The benchmark exercises the direct local Mistral function-calling architecture without Streamlit.

For every operator turn, Mistral receives the complete supported function catalog plus recent conversation history and compact authoritative state. It selects one function. Python validates/resolves arguments and executes deterministic network logic; the evidence is then explained by Mistral and checked by the grounding guardrail.

There is no coordinator or deterministic intent router in the benchmark path.

## Development suite

```powershell
python tests\llm\evaluate.py --query-set operator_manual_5x10_v1.json --all
```

This runs 10 categories x 5 manually verified queries.

## Gold suite

```powershell
python tests\llm\evaluate.py --query-set operator_10_categories_v1.json --all
```

This runs 10 categories x 10 queries. Keep this set held out from future fine-tuning.

## Multilingual conversational suite

```powershell
python tests\llm\evaluate.py --query-set operator_multilingual_context_v1.json --all
```

This exercises Italian and Portuguese conversational references against the same language-independent tool/state interface.

Results are written to `tests/llm/results/v1/` and are intentionally not shipped pre-populated in clean distributions.
