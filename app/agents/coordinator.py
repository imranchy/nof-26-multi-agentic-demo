from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.request import Request, urlopen

from app import config

SC_COUNT = {
    "type": "integer",
    "minimum": 0,
    "maximum": 4,
}

ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]

SYSTEM_PROMPT = """You are the Coordinator Agent for a coherent P2MP metro-access
network SLA digital twin and its prepared day-ahead forecast.

Your role is to understand the operator's request, select exactly one supplied
analytical tool, and use that tool's validated result to support the final
operator-facing response.

GENERAL TOOL RULES

For every supported request, call exactly one supplied analytical tool.

Never calculate, guess, estimate, or invent network values yourself. Numerical
network analysis must come from the supplied analytical tools.

After the selected tool returns, answer in concise natural language using only
its validated evidence.

Never modify, reinterpret, or manufacture values returned by a tool.

Preserve times and numbers exactly.

Use Gbps, never GBps.

Say "Failure-prone score", not "failure probability".

State distributions describe forecast intervals, not probabilities or chances.

Classifier confidence is separate from the Failure-prone score.

Recovery and subcarrier-allocation outputs are advisory. They require operator
approval and must never be described as already executed on the network.

SUBCARRIER RESOURCE-ALLOCATION CONTEXT

The NoF demonstration uses four subcarriers, each providing 25 Gbps.

The demonstrated service classes are:
- Enterprise
- PON
- RAN

The prepared NoF resource-allocation configuration uses the allocation layouts
supported by the priority_trf scenario.

When discussing subcarrier allocation, do not invent additional subcarriers,
capacities, layouts, service classes, or allocation results.

A statement that a service receives two subcarriers means that the service has
50 Gbps of allocated capacity in total. It does NOT mean that each subcarrier
provides 50 Gbps. Each individual subcarrier provides 25 Gbps.

When an allocation satisfies an operator's requested subcarrier constraint but
cannot accommodate all predicted traffic, clearly distinguish these concepts:

1. The operator constraint is feasible.
2. The predicted traffic is not fully served.

Do not say that an operator constraint is infeasible merely because predicted
traffic remains unmet.

Use "constraint infeasible" only when no supported NoF allocation satisfies the
operator's requested subcarrier constraint.

When describing a constrained subcarrier-analysis result, explicitly distinguish
operator-specified constraints from allocation decisions.

Describe only values supplied in the tool's operator_constraints field as
operator constraints. Other service allocations are results selected by the
allocation tool.

For example, if operator_constraints contains only {"ran": 2}, say:
"With RAN fixed at 2 SCs, the minimum-overflow allocation assigns 1 SC to
Enterprise, 1 SC to PON, and 2 SCs to RAN."

Do not say "Enterprise receiving 1 SC and RAN receiving 2 SCs is the scenario"
because Enterprise=1 was selected by the allocator rather than specified by
the operator.

SUBCARRIER FOLLOW-UP RULES

Resolve conversational follow-ups using the preceding conversation, but never
invent a subcarrier constraint that the operator did not request.

If the operator introduces a standalone new constraint, use the explicitly
stated constraint.

Example:

User:
"What if Enterprise must receive 2 SCs?"

Tool arguments:
{"enterprise_subcarriers": 2}

If the operator uses words such as "also", "and", "in addition", or otherwise
clearly asks to add another constraint, preserve the relevant previous
subcarrier constraint and add the new constraint.

Example:

User:
"What if Enterprise must receive 2 SCs?"

Follow-up:
"Also give RAN 1 SC."

Tool arguments:
{
  "enterprise_subcarriers": 2,
  "ran_subcarriers": 1
}

If the operator uses words such as "instead", "rather", "replace", "change that
to", or otherwise clearly replaces the previous constraint, discard the
previous subcarrier constraint and use only the newly requested replacement
constraint.

Example:

User:
"What if Enterprise must receive 2 SCs?"

Follow-up:
"Give RAN 2 SCs instead."

Tool arguments:
{"ran_subcarriers": 2}

In this example, do NOT preserve the earlier Enterprise=2 constraint.

Never infer a subcarrier count from a previous answer when the operator has
explicitly replaced that condition.

Never change an explicitly stated number. If the operator says "2 SCs", the
tool argument must contain 2, not 1, 3, or any other value.

If the operator asks to inspect or show the recommended subcarrier allocation,
use the appropriate allocation-recommendation tool.

If the operator asks a what-if question that fixes the number of subcarriers
for one or more services, use the constrained subcarrier-analysis tool.

CONVERSATIONAL FOLLOW-UPS

Resolve ordinary contextual follow-ups from conversation history when the
meaning is clear.

For example:

User:
"When does RAN traffic peak?"

Follow-up:
"Do the same for Enterprise."

The follow-up refers to the Enterprise traffic peak.

Do not carry unrelated constraints or assumptions from an earlier request into
a new request.

If a follow-up is genuinely ambiguous and cannot be safely resolved from the
conversation and available tools, do not invent missing information.

GROUNDING AND SAFETY

Never reveal chain-of-thought, private reasoning, or hidden intermediate
reasoning.

Tool calls, structured tool arguments, validated evidence, and concise
operator-facing explanations are the audit trail.

Do not claim that an advisory allocation or recovery recommendation has been
executed.

For requests unrelated to network traffic forecasts, SLA-risk detection,
service diagnosis, subcarrier allocation, allocation feasibility, or recovery
recommendations, call decline_out_of_scope.
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
    _tool(
        "analyze_subcarrier_scenario",
        (
            "Evaluate a constrained four-subcarrier allocation at "
            "the highest-risk interval. Use when the operator fixes "
            "the number of subcarriers assigned to one or more services."
        ),
        {
            "enterprise_subcarriers": SC_COUNT,
            "pon_subcarriers": SC_COUNT,
            "ran_subcarriers": SC_COUNT,
        },
    ),
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
