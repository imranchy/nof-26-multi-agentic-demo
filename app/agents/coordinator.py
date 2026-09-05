from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.request import Request, urlopen

from app import config

ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]

SYSTEM_PROMPT = """You are the Coordinator Agent for a coherent P2MP metro-access
network SLA digital twin and its prepared day-ahead forecast.

For every supported request, call exactly one supplied analytical tool. Never
calculate, guess, or invent network values. After the tool returns, answer in
concise natural language using only its validated evidence.

Preserve times and numbers exactly. Use Gbps, never GBps. Say "Failure-prone
score", not "failure probability". State distributions describe forecast
intervals, not chances. Classifier confidence is separate from the
Failure-prone score. Recovery output is advisory, requires operator approval,
and has not been executed. Resolve follow-ups such as "Do the same for PON"
from the conversation. Never reveal chain-of-thought; tool calls and validated
results are the audit trail. For unrelated requests call decline_out_of_scope.
"""


def _tool(name: str, description: str, properties: dict[str, Any] | None = None,
          required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


SERVICE = {"type": "string", "enum": ["enterprise", "ran", "pon"]}
TOOLS = [
    _tool("summarize_day_ahead", "Summarize the full forecast, state counts, and peak risk."),
    _tool(
        "find_next_sla_risk",
        "Find the earliest non-normal interval, optionally restricted to one risk state.",
        {"state": {"type": "string", "enum": ["any_non_normal", "degraded", "failure_prone"]}},
        ["state"],
    ),
    _tool("find_highest_risk", "Return the interval with the highest Failure-prone score."),
    _tool("find_service_peak", "Find the single peak time and load for one service.", {"service": SERVICE}, ["service"]),
    _tool(
        "rank_service_intervals",
        "Return the top N traffic intervals for one service; do not use for a singular peak question.",
        {"service": SERVICE, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}},
        ["service", "top_k"],
    ),
    _tool("diagnose_highest_risk", "Identify the dominant service at the highest-risk interval."),
    _tool("recommend_subcarrier_allocation", "Recommend the minimum-overflow four-subcarrier allocation at peak risk."),
    _tool("check_allocation_feasibility", "Check whether that allocation accommodates all predicted peak-risk traffic."),
    _tool(
        "compare_service_loads",
        "Compare Enterprise, RAN, and PON daily loads.",
        {"statistic": {"type": "string", "enum": ["mean", "maximum"]}},
        ["statistic"],
    ),
    _tool("get_state_distribution", "Return SLA-state counts and percentages."),
    _tool("validate_forecast", "Report deterministic validation checks."),
    _tool("decline_out_of_scope", "Use for requests unrelated to network forecasts, SLA risk, diagnosis, allocation, or recovery."),
]


class CoordinatorAgent:
    """Run native Ollama tool-calling turns and retain conversation context."""

    def __init__(self, use_llm: bool = True) -> None:
        if not use_llm:
            raise ValueError("Native tool-calling mode requires use_llm=True.")
        self.history: list[dict[str, Any]] = []

    def run(self, query: str, execute_tool: ToolExecutor) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.history[-12:],
            {"role": "user", "content": query},
        ]
        try:
            selection = self._chat(messages, include_tools=True)
            calls = selection.get("tool_calls") or []
            if not calls:
                messages.append(selection)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Select and call exactly one available tool for this "
                            "request. Do not answer before calling a tool."
                        ),
                    }
                )
                selection = self._chat(messages, include_tools=True)
                calls = selection.get("tool_calls") or []
                if not calls:
                    raise RuntimeError("Mistral returned no analytical tool call.")
            function = calls[0].get("function", {})
            name = str(function.get("name", ""))
            if name not in {tool["function"]["name"] for tool in TOOLS}:
                raise ValueError(f"Mistral requested unknown tool: {name}")
            arguments = self._arguments(function.get("arguments", {}))
            evidence = execute_tool(name, arguments)

            messages.extend([
                selection,
                {"role": "tool", "tool_name": name, "content": json.dumps(evidence, ensure_ascii=False)},
            ])
            # The second turn must synthesize the supplied evidence rather than
            # selecting another tool.
            final = self._chat(messages, include_tools=False)
            answer = str(final.get("content", "")).strip()
            if not answer:
                raise RuntimeError("Mistral returned an empty operator response.")

            self.history.extend([
                {"role": "user", "content": query}, selection, messages[-1],
                {"role": "assistant", "content": answer},
            ])
            self.history = self.history[-12:]
            return answer, name, arguments, evidence
        except Exception as exc:
            raise RuntimeError(
                "The Mistral tool-calling coordinator is unavailable. Confirm that "
                "Ollama is running and mistral:7b is installed. "
                f"Technical detail: {type(exc).__name__}: {exc}"
            ) from exc

    def reset(self) -> None:
        self.history.clear()

    def _chat(
        self,
        messages: list[dict[str, Any]],
        include_tools: bool,
    ) -> dict[str, Any]:
        """Select a tool with structured output, then synthesize its evidence."""
        conversation = self._render_messages(messages)

        if include_tools:
            prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                "Available analytical tools:\n"
                f"{json.dumps(TOOLS, ensure_ascii=False)}\n\n"
                "Conversation:\n"
                f"{conversation}\n\n"
                "Select exactly one tool. Return a JSON object containing "
                "the exact tool name and its arguments. Do not answer the "
                "operator yet."
            )
            output_format: str | dict[str, Any] | None = {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": [tool["function"]["name"] for tool in TOOLS],
                    },
                    "arguments": {"type": "object"},
                },
                "required": ["name", "arguments"],
            }
        else:
            prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                "The selected specialist tool has now been executed. "
                "Answer the operator using only the validated tool result "
                "in the conversation below.\n\n"
                f"{conversation}\n\n"
                "Return only the concise operator-facing answer. "
                "Do not include JSON, tool syntax, analysis, or hidden reasoning."
            )
            output_format = None

        payload = {
            "model": config.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 220,
            },
        }
        if output_format is not None:
            payload["format"] = output_format

        request = Request(
            f"{config.OLLAMA_URL}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        with urlopen(request, timeout=60) as response:
            body = json.loads(response.read())

        generated_text = str(body.get("response", "")).strip()

        if not generated_text:
            raise RuntimeError("Mistral returned an empty response.")

        if not include_tools:
            return {
                "role": "assistant",
                "content": generated_text,
            }

        try:
            selected = json.loads(generated_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Mistral returned invalid tool-selection JSON: {generated_text[:300]}"
            ) from exc

        if not isinstance(selected, dict):
            raise RuntimeError("Mistral tool selection was not a JSON object.")

        name = selected.get("name")
        arguments = selected.get("arguments", {})
        allowed_names = {tool["function"]["name"] for tool in TOOLS}
        if name not in allowed_names:
            raise RuntimeError(f"Mistral selected an unknown tool: {name}")
        if not isinstance(arguments, dict):
            raise RuntimeError(f"Arguments for {name} were not a JSON object.")

        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "index": 0,
                        "name": name,
                        "arguments": arguments,
                    },
                }
            ],
        }


    @staticmethod
    def _render_messages(
        messages: list[dict[str, Any]],
    ) -> str:
        """Render conversation context for Mistral's raw prompt."""
        rendered: list[str] = []

        for message in messages:
            role = str(message.get("role", "user")).upper()
            content = str(message.get("content", "")).strip()

            if role == "SYSTEM":
                continue

            if message.get("tool_calls"):
                calls = []

                for call in message["tool_calls"]:
                    function = call.get("function", {})
                    calls.append(
                        {
                            "name": function.get("name"),
                            "arguments": function.get(
                                "arguments",
                                {},
                            ),
                        }
                    )

                rendered.append(
                    "ASSISTANT TOOL CALL: "
                    + json.dumps(
                        calls,
                        ensure_ascii=False,
                    )
                )
                continue

            if role == "TOOL":
                tool_name = message.get(
                    "tool_name",
                    "unknown_tool",
                )

                rendered.append(
                    f"VALIDATED TOOL RESULT "
                    f"({tool_name}): {content}"
                )
                continue

            rendered.append(
                f"{role}: {content}"
            )

        return "\n".join(rendered)

    @staticmethod
    def _arguments(value: Any) -> dict[str, Any]:
        """Normalize tool arguments returned by Mistral."""
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError("Tool arguments contain invalid JSON.") from exc
            if isinstance(parsed, dict):
                return parsed
        raise ValueError("Tool arguments must be a JSON object.")
