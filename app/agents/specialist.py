from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from app import config
from app.agents.tool_catalog import ALL_TOOL_NAMES, tool_schemas


class LocalSpecialistAgent:
    """Direct local Mistral tool router.

    Primary path:
        Ollama native tool calling.

    Recovery path:
        Mistral structured-output repair when the local model identifies
        the capability correctly but does not emit Ollama's tool_calls
        envelope.

    Mistral always decides which capability to use.
    Python only validates the structured decision.
    """

    def __init__(self, use_llm: bool = True) -> None:
        self.use_llm = use_llm
        self.last_audit: dict[str, Any] = {}

    def select_tool(
        self,
        query: str,
        context_memory: dict[str, Any],
        conversation_history: list[dict[str, Any]],
        allowed_tools_override: tuple[str, ...] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        if not self.use_llm:
            raise RuntimeError("LLM tool selection is disabled.")

        allowed_tools = tuple(
            allowed_tools_override or ALL_TOOL_NAMES
        )

        if not allowed_tools:
            raise ValueError(
                "At least one local tool must be available."
            )

        tools = tool_schemas(allowed_tools)

        #
        # Keep this intentionally short.
        # The detailed semantics already live in each tool description.
        #
        system_prompt = config.tool_router_prompt()

        user_content = f"""
Operational state:
{json.dumps(context_memory, ensure_ascii=False)}

Recent conversation:
{json.dumps(conversation_history[-4:], ensure_ascii=False)}

Operator request:
{query}
""".strip()

        native_payload = {
            "model": config.OLLAMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            "tools": tools,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 192,
            },
        }

        #
        # Stage 1:
        # Normal Ollama native tool calling.
        #
        native_body = self._post_chat(native_payload)

        message = native_body.get("message", {})

        if not isinstance(message, dict):
            message = {}

        tool_calls = message.get("tool_calls", [])
        content = str(message.get("content", "") or "").strip()

        if tool_calls:
            try:
                name, arguments = (
                    self._validate_native_tool_calls(
                        tool_calls,
                        allowed_tools,
                    )
                )

                self.last_audit = {
                    "prompt_version": config.prompt_version("tool_router"),
                    "mode": "ollama_native_tool_calling",
                    "native_success": True,
                    "repair_used": False,
                    "parse_failed": False,
                    "fallback_used": False,
                    "tool": name,
                    "arguments": arguments,
                    "content": content,
                    "tool_calls": tool_calls,
                }

                return name, arguments

            except Exception as exc:
                native_error = (
                    f"{type(exc).__name__}: {exc}"
                )
        else:
            native_error = (
                "Ollama returned no native tool_calls"
            )

        #
        # Stage 2:
        # Mistral itself repairs/serializes its decision into a strict
        # schema. Python does NOT infer intent from the operator query.
        #
        try:
            name, arguments, repair_body = (
                self._structured_tool_repair(
                    query=query,
                    context_memory=context_memory,
                    conversation_history=conversation_history,
                    allowed_tools=allowed_tools,
                    tools=tools,
                    native_content=content,
                )
            )

            self.last_audit = {
                "prompt_version": config.prompt_version("tool_router"),
                "mode": "ollama_native_with_structured_repair",
                "native_success": False,
                "repair_used": True,
                "parse_failed": False,
                "fallback_used": False,
                "native_error": native_error,
                "native_content": content,
                "native_tool_calls": tool_calls,
                "tool": name,
                "arguments": arguments,
                "repair_response": repair_body,
            }

            return name, arguments

        except Exception as repair_exc:
            self.last_audit = {
                "prompt_version": config.prompt_version("tool_router"),
                "mode": "ollama_native_with_structured_repair",
                "native_success": False,
                "repair_used": True,
                "parse_failed": True,
                "fallback_used": True,
                "native_error": native_error,
                "native_content": content,
                "native_tool_calls": tool_calls,
                "repair_error": (
                    f"{type(repair_exc).__name__}: "
                    f"{repair_exc}"
                ),
                "raw_response": native_body,
            }

            raise RuntimeError(
                "Mistral did not return one valid tool decision"
            ) from repair_exc

    def _structured_tool_repair(
        self,
        query: str,
        context_memory: dict[str, Any],
        conversation_history: list[dict[str, Any]],
        allowed_tools: tuple[str, ...],
        tools: list[dict[str, Any]],
        native_content: str,
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        """Ask Mistral to serialize its own tool decision.

        This is not deterministic routing. Mistral still chooses the
        function. Python only enforces the output schema.
        """

        schema = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "enum": list(allowed_tools),
                },
                "arguments": {
                    "type": "object",
                },
            },
            "required": [
                "name",
                "arguments",
            ],
            "additionalProperties": False,
        }

        compact_catalog = []

        for tool in tools:
            function = tool.get("function", {})

            compact_catalog.append(
                {
                    "name": function.get("name"),
                    "description": function.get(
                        "description",
                        "",
                    ),
                    "parameters": function.get(
                        "parameters",
                        {},
                    ),
                }
            )

        routing_instructions = config.tool_router_prompt()

        repair_prompt = f"""
Select exactly one network function for the operator request.

Follow these routing instructions and examples:
{routing_instructions}

Return only the structured object required by the response schema.

Available functions:
{json.dumps(compact_catalog, ensure_ascii=False)}

Operational state:
{json.dumps(context_memory, ensure_ascii=False)}

Recent conversation:
{json.dumps(conversation_history[-4:], ensure_ascii=False)}

Operator request:
{query}

Your previous attempted tool output was:
{native_content or "(none)"}

Decide the function yourself from the operator request and available
function descriptions. Re-evaluate the request from scratch; do not blindly copy
the previous attempted output if it violates the tool descriptions or context rules.

Context rules:
- Relative-time expressions such as "one hour later", "30 minutes earlier",
  or "at that time" require a real previous reference timestamp.
- If Recent conversation and Operational state contain no previous timestamp and
  the request depends only on relative time, choose request_clarification with
  missing_field="reference_time".
- Never put a phrase such as "one hour later" into an absolute `time` field.
- If the request contains an explicit absolute timestamp such as 21:15, use it directly.
- Resource-allocation wording such as "remaining capacity", "remaining two
  subcarriers", "the rest", or "allocate what is left" is NOT relative-time
  language and must never trigger request_clarification(reference_time).

For analyze_constrained_allocation:
- Use the `constraints` array.
- Include only services explicitly constrained by the current operator request.
- Never add zero-valued entries for unconstrained services.
- Never infer how remaining capacity should be allocated.
- "Allocate the remaining" is an instruction for deterministic Python, not an
  additional constraint.

Do not emit relative_time_offset_minutes=0 for an absolute-time request. Use that
field only when the current operator request actually expresses a relative time shift.
Do not calculate network results.
Do not answer the operator in prose.
Do not invent missing values.
""".strip()

        payload = {
            "model": config.OLLAMA_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": repair_prompt,
                }
            ],
            "format": schema,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 192,
            },
        }

        body = self._post_chat(payload)

        message = body.get("message", {})

        if not isinstance(message, dict):
            raise ValueError(
                "structured repair returned no message"
            )

        raw = str(
            message.get("content", "") or ""
        ).strip()

        if not raw:
            raise ValueError(
                "structured repair returned empty content"
            )

        try:
            decision = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid structured repair JSON: {exc}"
            ) from exc

        if not isinstance(decision, dict):
            raise ValueError(
                "structured repair result must be an object"
            )

        name = str(
            decision.get("name", "")
        ).strip()

        if name not in allowed_tools:
            raise ValueError(
                f"tool {name!r} is not available"
            )

        arguments = decision.get(
            "arguments",
            {},
        )

        if arguments is None:
            arguments = {}

        if not isinstance(arguments, dict):
            raise ValueError(
                "structured arguments must be an object"
            )

        return name, dict(arguments), body

    @staticmethod
    def _post_chat(
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        request = Request(
            f"{config.OLLAMA_URL}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
        )

        with urlopen(
            request,
            timeout=90,
        ) as response:
            body = json.loads(
                response.read()
            )

        if not isinstance(body, dict):
            raise ValueError(
                "Ollama returned an invalid response"
            )

        return body

    @staticmethod
    def _validate_native_tool_calls(
        tool_calls: list[dict[str, Any]],
        allowed_tools: tuple[str, ...],
    ) -> tuple[str, dict[str, Any]]:
        if not isinstance(tool_calls, list):
            raise ValueError(
                "tool_calls must be a list"
            )

        if len(tool_calls) != 1:
            raise ValueError(
                "exactly one tool call is required"
            )

        call = tool_calls[0]

        if not isinstance(call, dict):
            raise ValueError(
                "tool call must be an object"
            )

        function = call.get("function")

        if not isinstance(function, dict):
            raise ValueError(
                "tool call must contain a function object"
            )

        name = str(
            function.get("name", "")
        ).strip()

        if not name:
            raise ValueError(
                "function name is required"
            )

        if name not in allowed_tools:
            raise ValueError(
                f"tool {name!r} is not available"
            )

        arguments = function.get(
            "arguments",
            {},
        )

        if isinstance(arguments, str):
            try:
                arguments = json.loads(
                    arguments or "{}"
                )
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "invalid function arguments JSON"
                ) from exc

        if arguments is None:
            arguments = {}

        if not isinstance(arguments, dict):
            raise ValueError(
                "function arguments must be an object"
            )

        return name, dict(arguments)