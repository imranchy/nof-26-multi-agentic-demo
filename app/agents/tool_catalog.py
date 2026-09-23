from __future__ import annotations

from typing import Any

from app import config


def _policy_ids() -> list[str]:
    return sorted(path.stem.upper() for path in config.POLICY_DIR.glob("*.yaml"))


def _objective_ids() -> list[str]:
    cfg = config.load_yaml("recommendation.yaml")["recommendation"]
    return list(cfg.get("objectives", {}).keys())


def _policy_description() -> str:
    parts = []
    for policy_id in _policy_ids():
        meta = config.load_policy_yaml(policy_id)
        parts.append(f"{policy_id}={meta.get('name', policy_id)}: {meta.get('operator_role', meta.get('objective', 'configured policy'))}")
    return "Configured allocation policy. " + "; ".join(parts) + "."


def _objective_description() -> str:
    cfg = config.load_yaml("recommendation.yaml")["recommendation"]
    parts = [
        f"{name}={details.get('description', name)}"
        for name, details in cfg.get("objectives", {}).items()
    ]
    return "Configured policy-selection objective. " + "; ".join(parts) + ". An objective is not a hard SC-count constraint."


POLICY = {
    "type": "string",
    "enum": _policy_ids(),
    "description": _policy_description(),
}
TIME = {
    "type": "string",
    "pattern": r"^([01]?\d|2[0-3]):[0-5]\d$|^(0?[1-9]|1[0-2]):[0-5]\d\s?(AM|PM|am|pm)$",
    "description": "Absolute clock time. Prefer canonical 24-hour HH:MM. Omit when the user clearly refers to the previously stored time.",
}
RELATIVE_OFFSET = {
    "type": "integer",
    "minimum": -1440,
    "maximum": 1440,
    "description": (
        "Relative offset in minutes from the authoritative previous timestamp. "
        "Emit this field ONLY when the current operator utterance explicitly "
        "expresses a relative clock-time shift such as one hour later or "
        "30 minutes earlier. Do not use resource-allocation wording such as "
        "'remaining capacity' or 'remaining two subcarriers' as relative time. "
        "Do NOT emit 0 for an absolute timestamp. Python performs the arithmetic."
    ),
}
OBJECTIVE = {
    "type": "string",
    "enum": _objective_ids(),
    "description": _objective_description(),
}
SC_COUNT = {"type": "integer", "minimum": 0, "maximum": 4}
SC_CONSTRAINTS = {
    "type": "array",
    "description": (
        "Only the SC-count constraints explicitly stated by the operator. "
        "Do not add entries for unconstrained services. If the operator says "
        "to allocate the remaining capacity, that does not create additional "
        "constraint entries."
    ),
    "items": {
        "type": "object",
        "properties": {
            "service": {"type": "string", "enum": ["enterprise", "ran", "pon"]},
            "subcarriers": {"type": "integer", "minimum": 0, "maximum": 4},
        },
        "required": ["service", "subcarriers"],
        "additionalProperties": False,
    },
}
METRIC = {
    "type": "string",
    "enum": ["failure_probability", "total_gbps", "blocking", "reconfiguration"],
}
SLA_STATE = {"type": "string", "enum": ["normal", "degraded", "failure_prone"]}


def _single_time(properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"time": TIME, "relative_time_offset_minutes": RELATIVE_OFFSET, **(properties or {})}


def _function_tool(name: str, description: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "additionalProperties": False,
            },
        },
    }


TOOLS: dict[str, dict[str, Any]] = {
    item["function"]["name"]: item
    for item in [
        _function_tool(
            "get_traffic_forecast",
            "Predict offered traffic only at one timestamp: Enterprise, RAN, PON and total Gbps. Use for traffic/load/busy/outlook questions, not complete network state.",
            _single_time(),
        ),
        _function_tool(
            "get_sla_prediction",
            "Predict SLA state and Failure-prone risk at one timestamp. Use for direct SLA/risk questions that do not ask why/explain a stated claim.",
            _single_time(),
        ),
        _function_tool(
            "explain_sla_risk",
            "Explain or correct an SLA-state/risk claim at one timestamp using validated evidence. Use for why/explain/correct-premise questions; do not additionally call get_sla_prediction.",
            _single_time({"claimed_state": SLA_STATE}),
        ),
        _function_tool(
            "get_network_state_at_time",
            "Return a complete network-state snapshot at one timestamp: traffic, SLA risk/state and SC allocation/policy state. Do not use for traffic-only, SLA-only or named-policy counterfactual questions.",
            _single_time({"policy": POLICY}),
        ),
        _function_tool(
            "compare_policies_at_time",
            "Compare configured policies at one timestamp and choose/recommend according to an optimization objective such as balanced, minimum blocking, minimum reconfiguration, or SLA priority. Optimization preferences are objectives, not hard SC constraints.",
            _single_time({"objective": OBJECTIVE}),
        ),
        _function_tool(
            "simulate_policy_at_time",
            "Evaluate the counterfactual outcome of one explicitly named policy at one timestamp. Use when the operator asks how PCA/MBA/SAA would perform or what that named policy would produce.",
            _single_time({"policy": POLICY}),
        ),
        _function_tool(
            "analyze_constrained_allocation",
            (
                "Evaluate explicit hard SC-count constraints. Represent operator-stated "
                "service constraints only in the 'constraints' list. For example, "
                "'keep RAN on 2 SCs' means constraints=[{'service':'ran','subcarriers':2}]. "
                "Do not create constraint entries for Enterprise or PON unless the operator "
                "explicitly constrains them. 'Allocate the remaining' does not create "
                "additional constraints; deterministic Python allocates unconstrained "
                "remaining capacity. Optimization preferences such as minimum blocking or "
                "minimum reconfiguration belong in 'objective', not in the constraints list."
            ),
            _single_time({
                "constraints": SC_CONSTRAINTS,
                "reference_policy": POLICY,
                "objective": OBJECTIVE,
            }),
        ),
        _function_tool(
            "compare_network_states",
            "Compare two explicit network timestamps and report changes/deltas. Use only when the operator requests a two-time comparison, difference, change, before/after, or delta.",
            {"time_a": TIME, "time_b": TIME, "policy": POLICY},
        ),
        _function_tool(
            "find_risk_intervals",
            "Rank and return top-k day-ahead intervals by Failure-prone risk, total load, blocking, or reconfiguration. Use for highest/worst/top interval discovery, not a continuous range summary.",
            {"metric": METRIC, "top_k": {"type": "integer", "minimum": 1, "maximum": 10}},
        ),
        _function_tool(
            "summarize_time_range",
            "Summarize a continuous start-to-end time window, including traffic, SLA distribution and policy behavior. Use for an explicit time range/window, not top-k interval discovery.",
            {"start_time": TIME, "end_time": TIME, "objective": OBJECTIVE},
        ),
        _function_tool(
            "request_clarification",
            (
                "Ask the operator for essential missing conversational context. "
                "For a relative clock-time request with no previous timestamp, use "
                "missing_field='reference_time'. Do not use this merely because a "
                "network-allocation request refers to remaining capacity or remaining "
                "subcarriers. If the current request provides an explicit absolute "
                "timestamp, that timestamp does not require a reference time."
            ),
            {
                "missing_field": {
                    "type": "string",
                    "enum": ["reference_time", "time", "policy", "objective", "constraint", "other"],
                }
            },
        ),
        _function_tool(
            "decline_physical_layer",
            "Use only for unsupported physical-layer requests such as OSNR, BER, Q-factor, fiber-cut propagation or GNPy analysis.",
        ),
        _function_tool(
            "decline_out_of_scope",
            "Use only for requests outside this network demonstrator's supported analytical scope.",
        ),
    ]
}

ALL_TOOL_NAMES: tuple[str, ...] = tuple(TOOLS)


def tool_schemas(names: tuple[str, ...] | list[str] | None = None) -> list[dict[str, Any]]:
    selected = ALL_TOOL_NAMES if names is None else tuple(names)
    unknown = [name for name in selected if name not in TOOLS]
    if unknown:
        raise ValueError(f"Unknown tool schema(s): {unknown}")
    return [TOOLS[name] for name in selected]


def argument_names(tool_name: str) -> set[str]:
    params = TOOLS[tool_name]["function"]["parameters"]
    return set(params.get("properties", {}).keys())
