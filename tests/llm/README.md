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
