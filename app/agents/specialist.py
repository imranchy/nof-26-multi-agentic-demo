from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from app import config
from app.agents.tool_catalog import ALL_TOOL_NAMES, tool_schemas


class LocalSpecialistAgent:
    """Local Mistral raw function-calling selector.

    Mistral selects exactly one registered local function and its structured
    arguments using Mistral 7B v0.3's raw function-calling protocol.

    Python remains responsible for:
    - validation
    - inherited state
    - precedence
    - clock arithmetic
    - constraint merging
    - deterministic network execution

    No operator-language phrase routing is implemented here.
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

        allowed_tools = tuple(allowed_tools_override or ALL_TOOL_NAMES)

        if not allowed_tools:
            raise ValueError("At least one local tool must be available.")

        inherited_lock = (
            context_memory.get("last_tool")
            if len(allowed_tools) == 1
            and context_memory.get("last_tool") in allowed_tools
            else None
        )

        tools = tool_schemas(allowed_tools)

        system_prompt = """
You are the function-selection layer of a local optical-network operations assistant.

Your only task is to select exactly one available function.

The operator request may be:
- English
- Italian
- Portuguese
- code-switched technical language

Use the semantic meaning of the request, not literal phrase matching.

Capability rules:

- Traffic/load/forecast at one timestamp:
  get_traffic_forecast

- Direct SLA state or Failure-prone risk:
  get_sla_prediction

- Explain, verify or correct an SLA state/risk claim:
  explain_sla_risk

- Complete network snapshot at one timestamp:
  get_network_state_at_time

- Compare policies or choose the best policy according to an objective:
  compare_policies_at_time

- Evaluate what one explicitly named policy would produce:
  simulate_policy_at_time

- Evaluate explicit hard SC-count reservations or assignments:
  analyze_constrained_allocation

- Compare network conditions at two timestamps:
  compare_network_states

- Find highest/worst/top-k intervals:
  find_risk_intervals

- Summarize one continuous start-to-end time range:
  summarize_time_range

Important distinctions:

- An optimization preference is NOT a hard SC-count constraint.
- Minimum blocking, fewest reconfigurations, stability, or SLA priority are policy objectives.
- Explicit assignments such as RAN=2 SCs or reserve 1 SC for PON are hard constraints.
- A named-policy hypothetical is a counterfactual, not a complete network snapshot.
- A broader function is not equivalent to the specifically requested function.
- A relative-time follow-up does not automatically imply comparison.
- Do not calculate network values.
- Do not perform clock arithmetic.
- Do not answer the operator in prose.
- Do not invent timestamps, policies, objectives, SC counts, or network values.
- Call exactly one function.
""".strip()

        user_content = f"""
Validated context state eligible for this turn:
{json.dumps(context_memory, ensure_ascii=False)}

Inherited capability lock:
{json.dumps(inherited_lock, ensure_ascii=False)}

Recent structured conversation history:
{json.dumps(conversation_history[-4:], ensure_ascii=False)}

Current operator request:
{query}

Select exactly one available function.

Include only arguments that are explicit in the current operator request.
Validated inherited values and defaults are applied later by deterministic Python.
""".strip()

        attempts: list[dict[str, Any]] = []

        for attempt_no in (1, 2):
            attempt_instruction = user_content

            if attempt_no == 2:
                attempt_instruction += """

Your previous response was not a valid function call.
Return exactly one function call using the required Mistral tool-call protocol.
Do not answer in prose.
"""

            raw_prompt = self._build_raw_prompt(
                tools=tools,
                system_prompt=system_prompt,
                user_content=attempt_instruction,
            )

            payload = {
                "model": config.OLLAMA_MODEL,
                "prompt": raw_prompt,
                "raw": True,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 220,
                },
            }

            try:
                request = Request(
                    f"{config.OLLAMA_URL}/api/generate",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )

                with urlopen(request, timeout=90) as response:
                    body = json.loads(response.read())

                raw_text = str(body.get("response", "")).strip()

                tool_name, arguments = self._parse_raw_tool_call(
                    raw_text=raw_text,
                    allowed_tools=allowed_tools,
                )

                self.last_audit = {
                    "mode": "mistral_raw_function_calling",
                    "attempts": attempts
                    + [
                        {
                            "attempt": attempt_no,
                            "ok": True,
                            "raw": raw_text,
                            "tool": tool_name,
                            "arguments": arguments,
                        }
                    ],
                    "parse_failed": False,
                    "fallback_used": False,
                }

                return tool_name, arguments

            except Exception as exc:
                attempts.append(
                    {
                        "attempt": attempt_no,
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        self.last_audit = {
            "mode": "mistral_raw_function_calling",
            "attempts": attempts,
            "parse_failed": True,
            "fallback_used": True,
        }

        raise RuntimeError(
            "Mistral did not return one valid raw function call"
        )

    @staticmethod
    def _validate_native_tool_calls(
        tool_calls: list[dict[str, Any]],
        allowed_tools: tuple[str, ...],
    ) -> tuple[str, dict[str, Any]]:
        """Validate one function call from Ollama's generic tool-call shape.

        Retained for compatibility with existing tests and older adapters.
        The active mistral:7b runtime path uses _parse_raw_tool_call().
        """

        if not isinstance(tool_calls, list):
            raise ValueError("tool_calls must be a list")

        if len(tool_calls) != 1:
            raise ValueError("exactly one tool call is required")

        call = tool_calls[0]

        if not isinstance(call, dict):
            raise ValueError("tool call must be an object")

        function = call.get("function")

        if not isinstance(function, dict):
            raise ValueError("tool call must contain a function object")

        name = str(function.get("name", "")).strip()

        if not name:
            raise ValueError("function name is required")

        if name not in allowed_tools:
            raise ValueError(
                f"tool {name!r} is not available for this turn"
            )

        arguments = function.get("arguments", {})

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid function arguments JSON: {exc}"
                ) from exc

        if arguments is None:
            arguments = {}

        if not isinstance(arguments, dict):
            raise ValueError("function arguments must be an object")

        return name, dict(arguments)

    @staticmethod
    def _build_raw_prompt(
        tools: list[dict[str, Any]],
        system_prompt: str,
        user_content: str,
    ) -> str:
        """Build Mistral 7B v0.3 raw function-calling prompt."""

        tools_json = json.dumps(
            tools,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return (
            f"[AVAILABLE_TOOLS] {tools_json}[/AVAILABLE_TOOLS]"
            f"[INST] {system_prompt}\n\n{user_content} [/INST]"
        )

    @staticmethod
    def _parse_raw_tool_call(
        raw_text: str,
        allowed_tools: tuple[str, ...],
    ) -> tuple[str, dict[str, Any]]:
        """Parse Mistral's [TOOL_CALLS] structured protocol.

        This parses only the model's machine-readable function-call protocol.
        It does not parse or interpret operator language.
        """

        if not raw_text:
            raise ValueError("empty Mistral response")

        marker = "[TOOL_CALLS]"

        if marker not in raw_text:
            raise ValueError(
                "Mistral response did not contain [TOOL_CALLS]"
            )

        payload_text = raw_text.split(marker, 1)[1].strip()

        # Some model/template variants may append EOS-like content.
        if "</s>" in payload_text:
            payload_text = payload_text.split("</s>", 1)[0].strip()

        decoder = json.JSONDecoder()

        try:
            calls, _ = decoder.raw_decode(payload_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid TOOL_CALLS JSON: {exc}"
            ) from exc

        if not isinstance(calls, list):
            raise ValueError(
                "TOOL_CALLS payload must be a list"
            )

        if len(calls) != 1:
            raise ValueError(
                "exactly one tool call is required"
            )

        call = calls[0]

        if not isinstance(call, dict):
            raise ValueError(
                "tool call must be an object"
            )

        name = str(call.get("name", "")).strip()

        if name not in allowed_tools:
            raise ValueError(
                f"tool {name!r} is not available for this turn"
            )

        arguments = call.get("arguments", {})

        if isinstance(arguments, str):
            arguments = json.loads(arguments or "{}")

        if arguments is None:
            arguments = {}

        if not isinstance(arguments, dict):
            raise ValueError(
                "tool arguments must be an object"
            )

        return name, dict(arguments)