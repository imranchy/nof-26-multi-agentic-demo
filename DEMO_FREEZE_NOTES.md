# Demo Freeze Notes

This build narrows the live presentation path around the final operator interactions and removes stale state leakage between standalone requests.

## Key changes

- Mistral routing now receives the current operator utterance without stale operational state or previous assistant answers.
- Deterministic Python still resolves omitted follow-up arguments after tool selection.
- Explicit-time SC constraint requests start a new constraint set.
- Time-omitting SC follow-ups may inherit the immediately previous constraint set and timestamp.
- Policy-selection objectives no longer inherit from unrelated prior turns.
- Network-state requests use the configured active policy unless the current request explicitly names another policy.
- Policy counterfactuals require an explicitly named policy.
- Tool execution receives already-resolved arguments rather than re-reading conversational memory.
- Non-constraint operations clear the previous SC-constraint thread.
- Policy YAML metadata now separates operator-facing role from implementation objective.
- Added the missing `sla_priority` tie-break order so that objective deterministically selects PCA.
- Active router remains `v3-english-contrastive`.
- Obsolete router prompt experiments were removed.

## Final demo interactions

1. What traffic is expected at 21:15?
2. What is the predicted SLA state at 21:15?
3. Show me the complete network state at 16:20.
4. Which allocation policy would you use at 21:15?
5. At 20:00, minimize blocking.
6. What happens if we use PCA at 21:15?
7. Keep RAN on 2 SCs at 19:00.
8. Also reserve one SC for PON.
9. What is the weather today?

## Validation

- `python -m pytest tests -q`
- Expected in this build: `61 passed`
