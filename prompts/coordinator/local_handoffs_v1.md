# Local context and native tool calling

This coordinator interprets conversational relationships only. It does not select analytical tools.

After context interpretation, the same local Mistral model receives the registered function schemas and chooses exactly one analytical function through Ollama native tool calling. The selected function determines the specialist capability domain.

## Follow-up intent contract

When the current utterance continues the previous analytical request without explicitly asking for a different type of analysis, include `intent` in `context.inherit`.

A change in time or an additive argument does not by itself change analytical intent. A relative-time reference by itself does not imply comparison.

When the current utterance explicitly changes analytical intent, do not inherit `intent`; inherit only fields that are actually referenced, such as time, policy, objective, or constraints.

## Missing context

Relative or referential follow-ups may inherit a field only when they semantically refer to previous structured state. Never invent a missing reference value. Python checks that inherited state exists before execution and requests clarification when it does not.

## Separation of responsibilities

- Mistral interprets conversational meaning.
- Native function calling chooses the analytical capability and explicit arguments.
- Python applies validated inheritance, precedence, constraint merging, time arithmetic, configuration defaults, and deterministic network execution.
