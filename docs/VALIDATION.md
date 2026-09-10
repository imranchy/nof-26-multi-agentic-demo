# Validation Plan

The poster validation is intentionally split into four layers so that model quality, network-algorithm correctness, semantic-agent behavior, and LLM grounding are not mixed together.

## 1. ML validation

The XGBoost day-ahead forecast is evaluated against the held-out target day's actual Enterprise/RAN/PON traffic and compared with a same-time previous-day persistence baseline. Report MAE, RMSE, and R² per service and aggregate summaries. The saved XGBoost model is also replayed and compared with the prepared frozen forecast; the repository requires agreement within 1e-5 Gbps.

The Random Forest report includes accuracy, macro/weighted F1, and Failure-prone precision/recall/F1. The single-scenario/random-interval-split limitation must remain visible.

Run:

```powershell
python -m scripts.build_validation_artifacts
```

## 2. Deterministic policy validation

Unit tests verify PCA priority semantics, MBA weighted residual-demand selection, SAA first-interval MBA equivalence, four-SC budget, traffic conservation, KPI bounds, operator-constraint preservation, and independent recomputation. The full-day policy replay summary is a demonstrator replay, not a claim to numerically reproduce every PSC-paper figure.

Run:

```powershell
python -m pytest -q
```

## 3. Mistral semantic-agent validation

`validation/query_sets/semantic_20_categories.json` contains 200 prompts across 20 operator-language categories (10 prompts each). Categories include ML tool selection, timestamped state, SLA explanation, policy objectives, constraints, cross-time comparison, range/risk discovery, recommendation history/change, evidence coverage, validation, follow-up context, bounded multi-tool use, and domain boundaries.

The evaluator records both the raw Mistral-proposed plan and the normalized/executed plan. Metrics include raw/executed tool-sequence accuracy, raw/executed argument accuracy, semantic-correction rate, and category-level results.

Quick smoke test:

```powershell
python -m scripts.evaluate_agent --limit 20
```

Full poster run:

```powershell
python -m scripts.evaluate_agent
```

## 4. LLM grounding / hallucination analysis

For every evaluated query, the raw Mistral explanation and final accepted answer are stored. The guardrail checks every numeric claim against deterministic evidence and rejects unsupported physical-layer diagnoses. Report raw explanation grounding-accept rate, guardrail fallback rate, unsupported-numeric-claim rate, and unsupported-physical-claim rate.

Generated files include:

```text
validation/results/agent_semantic_evaluation.csv
validation/results/agent_semantic_evaluation.json
validation/results/agent_semantic_summary.json
validation/results/agent_semantic_category_summary.csv
```

These results are intended for poster analysis; they are not pre-filled with fabricated scores.
