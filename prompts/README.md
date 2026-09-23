# Prompt modules

The NoF demonstrator keeps routing and explanation behavior in Markdown prompt modules rather than embedding long prompt text directly in Python.

## Tool router

The active and frozen demo router is configured in `config/prompts.yaml`:

- `tool_router/base_v3.md` — compact English routing rules and contrastive capability boundaries.
- `tool_router/few_shot_router_v3.md` — compact canonical examples for the supported demo intents.

The production demo intentionally keeps one router version only. Earlier multilingual-heavy and larger few-shot prompt experiments were removed after evaluation showed that the compact v3 prompt was more reliable for the local Mistral model.

Conversation state is not injected into the router for standalone intent selection. Python resolves only the arguments that are legitimately omitted by a follow-up, such as the timestamp and existing SC constraints in `Also reserve one SC for PON.`

## Explainer

The explainer is composed from its base prompt, category-specific module, and operator-style instructions.
