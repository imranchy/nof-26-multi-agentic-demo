# Deterministic / ML validation results

This folder is reserved for prediction-model and deterministic PSC-policy validation artifacts generated from the included data/models:

- `ml_forecast_vs_persistence.csv`
- `ml_validation_summary.json`
- `policy_replay_summary.csv`
- poster-ready copies under `poster_tables/`

Mistral semantic/hallucination benchmark results are deliberately kept separate under `tests/llm/results/v1/` so the Streamlit application and deterministic validation pipeline do not need to run the LLM benchmark.

Do not present placeholder LLM scores. Run the local category/full benchmark first and use the measured result files for the poster.
