# Mistral semantic and hallucination tests

These tests run without Streamlit. Ollama must be running with `mistral:7b` available.

The v1 operational benchmark contains **10 operator capabilities x 10 paraphrases = 100 queries**. Validation/evidence are not operator query categories; grounding and guardrails are measured internally.

## Recommended workflow

1. Validate the static gold set:
   `python -m tests.llm.validate_gold`
2. Run one category:
   `python -m tests.llm.evaluate --category traffic_prediction`
3. Review the JSON/CSV output under `tests/llm/results/v1/`.
4. Repeat category-by-category.
5. Once categories are acceptable, run the complete benchmark:
   `python -m tests.llm.evaluate --all`
6. Run adversarial/hallucination tests separately:
   `python -m tests.llm.evaluate_adversarial`

The report separates raw Mistral routing from guardrailed execution. This is intentional: raw LLM quality and complete-system reliability are different results.

## Local multilingual handoff benchmark

The local-agent architecture can be exercised without Streamlit. The coordinator first
selects a specialist handoff and conversational inheritance contract; the specialist
then emits its bounded structured capability call. Both stages use the local Ollama
Mistral model.

Italian and Portuguese conversational-context cases are in:

`tests/llm/query_sets/operator_multilingual_context_v1.json`

Run:

```powershell
python tests\llm\evaluate.py --query-set operator_multilingual_context_v1.json --all
```

The evaluator continues to record the raw specialist-proposed tool sequence and the
final executed sequence so agent routing errors remain observable rather than hidden by
Python language heuristics.
