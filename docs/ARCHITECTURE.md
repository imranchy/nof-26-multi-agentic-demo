# Direct local Mistral tool-routing architecture

The operator path contains no coordinator and no deterministic natural-language router.

1. `MultiAgentRuntime` exposes compact authoritative state and recent conversation history.
2. `LocalSpecialistAgent` sends that context plus the full function catalog to local `mistral:7b` through Ollama `/api/chat`.
3. Mistral returns exactly one native `message.tool_calls` function call.
4. Python validates structured arguments and resolves deterministic state requirements such as inherited time, relative-time arithmetic and SC-constraint merging.
5. `OperatorTools` executes deterministic ML/network/policy logic.
6. Mistral explains only returned evidence.
7. `GuardrailAgent` checks the explanation and replaces unsupported output with a deterministic fallback.

The function call itself is the semantic routing decision. Any capability labels shown in the UI are display metadata after the tool has already been selected; they do not control routing.
