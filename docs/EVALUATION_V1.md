# NoF v1 LLM evaluation protocol

The operator benchmark is intentionally independent of the Streamlit UI.

## Operational benchmark

`tests/llm/query_sets/operator_10_categories_v1.json`

- 10 operator capabilities
- 10 paraphrases per capability
- 100 queries total
- no XGBoost/Random-Forest/classifier wording in operator prompts
- follow-up cases use genuine setup turns

The ten categories are traffic prediction, SLA/risk state, full network state, balanced policy comparison, objective-aware recommendation, counterfactual policy analysis, SC constraints, temporal comparison, range/risk discovery, and conversational context.

## Evaluation sequence

Run `python -m tests.llm.validate_gold`, then evaluate one category at a time with `python -m tests.llm.evaluate --category <name>`. Review results in `tests/llm/results/v1/`. After category-level review, run `python -m tests.llm.evaluate --all`.

A separate adversarial set is available with `python -m tests.llm.evaluate_adversarial`.

## Metrics

Reports separate raw Mistral behavior from guardrailed system behavior: raw tool-plan accuracy, raw argument accuracy, executed tool/argument accuracy, deterministic correction rate, structured-output parse/fallback rate, raw explanation grounding acceptance, guardrail fallback, unsupported numeric/categorical/causal claims, implementation-detail exposure, and final safe-answer rate.

This separation is important: a corrected final answer is evidence of system reliability, not evidence that raw Mistral routing was correct.
