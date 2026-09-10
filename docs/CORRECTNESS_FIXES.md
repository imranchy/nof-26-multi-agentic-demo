# Correctness revision

This revision addresses issues found during the first live operator pilot.

- Normal operator answers are model-agnostic. Implementation model names remain in evidence/provenance only.
- SLA output shows predicted state plus Failure-prone risk; generic classifier-confidence wording is removed from operator-facing answers.
- Explicit SC-count language is deterministically protected from accidental routing to unrelated tools.
- SLA "why" questions are premise-aware: if the operator asserts the wrong predicted state, the system corrects the premise before explaining it.
- Recommendation-change questions first determine whether the recommendation actually changed.
- Range summaries aggregate the full requested period, including peak load/risk, state counts, per-policy blocking/reconfiguration summaries, and recommendation counts.
- Relative-time follow-ups preserve the prior analytical intent when unambiguous.
- Unused SC capacity is represented as IDLE in the operator-facing replay instead of being assigned to a service with no remaining demand.
- Numeric grounding is supplemented with categorical checks for SLA-state and recommendation/change claims.
- The frozen live traffic model is checked against the validated prepared held-out-day prediction baseline to catch accidental retraining/model replacement.
- The semantic benchmark remains 200 queries across 20 categories, with follow-up cases represented as actual setup turn + follow-up turn.

The deterministic test suite should be run with:

```bash
python -m pytest -q
```

The local-Mistral semantic benchmark should be run only after deterministic tests pass:

```bash
python -m scripts.evaluate_agent
```
