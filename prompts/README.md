# Prompt modules

The NoF demonstrator keeps routing and explanation behavior in versioned Markdown prompt modules rather than embedding long prompt text directly in Python.

## Tool router

The active router is configured in `config/prompts.yaml`.

Current version:

- `tool_router/base_v3.md` — concise language-agnostic routing rules and contrastive capability boundaries.
- `tool_router/few_shot_router_v3.md` — one compact English canonical example per evaluated category, plus the physical-layer scope boundary.

The router is intentionally instructed in English even though operator requests may be English, Italian, Portuguese, German, French, Spanish, or code-switched. The design relies on multilingual semantic understanding plus language-independent function schemas, instead of repeating every example in every language.

The previous files `base_v2.md` and `few_shot_multilingual_v1.md` may be retained for benchmark provenance/rollback, but they are no longer loaded by the active configuration.

## Explainer

The explainer remains composed from its base prompt, category-specific module, and operator-style instructions. Those files are unchanged by the v3 router update.
