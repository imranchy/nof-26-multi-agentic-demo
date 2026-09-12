# NoF prompt modules

## Direct tool router

The tool-selection stage uses:

1. `tool_router/base_v1.md`
2. `operator_style_v1.md`
3. the full registered function catalog from `app/agents/tool_catalog.py`
4. recent structured conversation history and compact authoritative state.

There is no coordinator prompt and no deterministic natural-language router.

## Explainer

The explainer concatenates:

1. `explainer/base_v1.md`
2. the module matching the executed evidence category
3. `operator_style_v1.md`

All network numbers, policy outcomes, and deterministic states must come from executed evidence rather than model invention.
