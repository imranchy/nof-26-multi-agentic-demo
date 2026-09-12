from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from app import config
from app.agents.local_agents import LOCAL_AGENT_SPECS

POLICY = {"type": "string", "enum": ["PCA", "MBA", "SAA"]}
TIME = {
    "type": "string",
    "pattern": r"^([01]\d|2[0-3]):[0-5]\d$",
    "description": "Canonical 24-hour HH:MM time.",
}
OBJECTIVE = {"type": "string", "enum": ["balanced", "min_blocking", "min_reconfiguration", "sla_priority"]}
SC_COUNT = {"type": "integer", "minimum": 0, "maximum": 4}
METRIC = {"type": "string", "enum": ["failure_probability", "total_gbps", "blocking", "reconfiguration"]}
SLA_STATE = {"type": "string", "enum": ["normal", "degraded", "failure_prone"]}


def _tool(name: str, description: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties or {},
            "additionalProperties": False,
        },
    }


TOOLS: dict[str, dict[str, Any]] = {
    item["name"]: item
    for item in [
        _tool("get_traffic_forecast", "Return predicted Enterprise, RAN, PON, and total offered traffic at one timestamp.", {"time": TIME}),
        _tool("get_sla_prediction", "Return predicted SLA state and Failure-prone risk at one timestamp.", {"time": TIME}),
        _tool("explain_sla_risk", "Explain/correct a predicted SLA state using validated risk evidence and concurrent traffic as non-causal context.", {"time": TIME, "claimed_state": SLA_STATE}),
        _tool("get_network_state_at_time", "Retrieve the complete network-state snapshot at one timestamp, optionally under one named policy.", {"time": TIME, "policy": POLICY}),
        _tool("compare_policies_at_time", "Compare PCA, MBA, and SAA at one timestamp and recommend according to an operator objective.", {"time": TIME, "objective": OBJECTIVE}),
        _tool("simulate_policy_at_time", "Return the counterfactual outcome of one named allocation policy at one timestamp.", {"time": TIME, "policy": POLICY}),
        _tool("analyze_constrained_allocation", "Evaluate explicit operator SC-count constraints and choose the best feasible four-SC assignment.", {
            "time": TIME,
            "enterprise_subcarriers": SC_COUNT,
            "ran_subcarriers": SC_COUNT,
            "pon_subcarriers": SC_COUNT,
            "reference_policy": POLICY,
            "objective": OBJECTIVE,
        }),
        _tool("compare_network_states", "Compare network state, traffic, SLA risk, and policy KPIs at two timestamps.", {"time_a": TIME, "time_b": TIME, "policy": POLICY}),
        _tool("find_risk_intervals", "Find top-k highest-risk, highest-load, highest-blocking, or highest-reconfiguration intervals.", {"metric": METRIC, "top_k": {"type": "integer", "minimum": 1, "maximum": 10}}),
        _tool("summarize_time_range", "Summarize traffic, SLA state distribution, policy blocking, reconfiguration, and recommendations over a continuous time range.", {"start_time": TIME, "end_time": TIME, "objective": OBJECTIVE}),
        _tool("decline_physical_layer", "Use for unsupported physical-layer requests such as OSNR, BER, Q-factor, fiber-cut, or GNPy analysis."),
        _tool("decline_out_of_scope", "Use for generic non-network requests."),
    ]
}

ARGUMENT_PROPERTIES: dict[str, Any] = {
    "time": TIME,
    "time_a": TIME,
    "time_b": TIME,
    "start_time": TIME,
    "end_time": TIME,
    "policy": POLICY,
    "reference_policy": POLICY,
    "objective": OBJECTIVE,
    "enterprise_subcarriers": SC_COUNT,
    "ran_subcarriers": SC_COUNT,
    "pon_subcarriers": SC_COUNT,
    "metric": METRIC,
    "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
    "claimed_state": SLA_STATE,
}


class LocalSpecialistAgent:
    """One local Mistral specialist selected by the coordinator handoff."""

    def __init__(self, use_llm: bool = True) -> None:
        self.use_llm = use_llm
        self.last_audit: dict[str, Any] = {}

    def plan(
        self,
        agent_name: str,
        query: str,
        context_memory: dict[str, Any],
        conversation_history: list[dict[str, Any]],
    ) -> list[tuple[str, dict[str, Any]]]:
        if not self.use_llm:
            raise RuntimeError("LLM specialist planning is disabled.")
        if agent_name not in LOCAL_AGENT_SPECS:
            raise ValueError(f"unknown local specialist: {agent_name}")

        spec = LOCAL_AGENT_SPECS[agent_name]
        tool_specs = [TOOLS[name] for name in spec.tools]
        prompt = f"""You are {agent_name}, a local specialist in an optical-network operations assistant.

Specialist responsibility:
{spec.description}

Allowed capabilities for this specialist:
{json.dumps(tool_specs, ensure_ascii=False)}

Validated context state eligible for this turn:
{json.dumps(context_memory, ensure_ascii=False)}

Recent structured conversation history:
{json.dumps(conversation_history[-4:], ensure_ascii=False)}

Current operator request:
{query}

Return the minimum schema-constrained capability plan for your responsibility.

Rules:
- Interpret natural language semantically in English, Italian, Portuguese, or code-switched technical language.
- Do not calculate network values.
- Emit only capabilities allowed for this specialist.
- Emit canonical structured arguments only when they are explicit in the current turn.
- Context state contains already validated inherited values; omit an argument when the current turn merely references inherited context and Python can apply it.
- Never invent timestamps, policies, objectives, constraints, metrics, or numerical network results.
- For an additive SC constraint follow-up, emit only the newly explicit SC counts; Python merges inherited constraints.
- For relative-time follow-ups, do not emit a guessed absolute timestamp; Python already applied the offset in context state.
- Preserve a specific inherited analytical intent. Do not broaden it into a more comprehensive capability merely because that capability includes the requested information.
- If the inherited context identifies a specific tool family or analytical intent, select the matching capability unless the current utterance explicitly asks for a different analysis.
- A broader result that happens to contain the requested information is not equivalent to the requested capability.
- Select `compare_network_states` only when the operator explicitly requests comparison, change, difference, delta, or another two-state analysis.
- Select `get_network_state_at_time` only when the operator requests a complete network-state snapshot; do not use it as a fallback for traffic-only or SLA-only requests.
- Use one step unless the operator explicitly asks for multiple capabilities owned by this same specialist.

Capability-selection discipline:
- Select the single minimum capability that directly answers the operator request.
- Do not add supporting, contextual, diagnostic, comparison, or state-retrieval capabilities merely because they might provide useful additional information.
- Use multiple capabilities only when the operator explicitly requests multiple distinct analytical outputs.
- A relative change of timestamp alone preserves the inherited analytical intent; it does not imply comparison.
- Select `compare_network_states` only when the operator explicitly asks to compare two network states, changes between times, differences, or deltas.
- For an SC-allocation constraint request, select `analyze_constrained_allocation` only unless the operator explicitly requests another analytical result as well.
- For a named-policy outcome, select `simulate_policy_at_time`; do not additionally retrieve network state unless explicitly requested.
- For a complete network-state request at one timestamp, select `get_network_state_at_time`; do not add comparison merely because a previous timestamp exists.
"""

        schema = self._output_schema(spec.tools)
        attempts: list[dict[str, Any]] = []
        for attempt_no in (1, 2):
            payload = {
                "model": config.OLLAMA_MODEL,
                "prompt": prompt if attempt_no == 1 else prompt + "\nThe previous plan failed validation. Return only a schema-valid specialist plan.",
                "stream": False,
                "format": schema,
                "options": {"temperature": 0, "num_predict": 320},
            }
            try:
                request = Request(
                    f"{config.OLLAMA_URL}/api/generate",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(request, timeout=90) as response:
                    body = json.loads(response.read())
                raw = str(body.get("response", "")).strip()
                selected = json.loads(raw)
                steps = self._validate_steps(agent_name, selected)
                self.last_audit = {
                    "agent": agent_name,
                    "attempts": attempts + [{"attempt": attempt_no, "ok": True, "raw": raw}],
                    "parse_failed": False,
                    "fallback_used": False,
                }
                return steps
            except Exception as exc:
                attempts.append({"attempt": attempt_no, "ok": False, "error": f"{type(exc).__name__}: {exc}"})

        # Fail closed inside the selected specialist's scope.
        fallback_tool = "decline_out_of_scope" if agent_name == "scope_agent" else None
        self.last_audit = {
            "agent": agent_name,
            "attempts": attempts,
            "parse_failed": True,
            "fallback_used": True,
        }
        if fallback_tool:
            return [(fallback_tool, {})]
        raise RuntimeError(f"local specialist {agent_name} could not produce a valid structured plan")

    @staticmethod
    def _output_schema(allowed_tools: tuple[str, ...]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 2,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "enum": list(allowed_tools)},
                            "arguments": {
                                "type": "object",
                                "properties": ARGUMENT_PROPERTIES,
                                "additionalProperties": False,
                            },
                        },
                        "required": ["name", "arguments"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["steps"],
            "additionalProperties": False,
        }

    @staticmethod
    def _validate_steps(agent_name: str, selected: Any) -> list[tuple[str, dict[str, Any]]]:
        if not isinstance(selected, dict):
            raise ValueError("specialist response must be an object")
        raw_steps = selected.get("steps")
        if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= 2:
            raise ValueError("specialist must return one or two steps")

        allowed = set(LOCAL_AGENT_SPECS[agent_name].tools)
        steps: list[tuple[str, dict[str, Any]]] = []
        for item in raw_steps:
            if not isinstance(item, dict):
                raise ValueError("specialist step must be an object")
            name = str(item.get("name", ""))
            arguments = item.get("arguments", {})
            if name not in allowed:
                raise ValueError(f"{agent_name} cannot call {name}")
            if not isinstance(arguments, dict):
                raise ValueError("specialist arguments must be an object")
            steps.append((name, dict(arguments)))
        return steps
