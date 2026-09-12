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
        parts.append(f"{policy_id}={meta.get('name', policy_id)} ({meta.get('objective', 'configured policy')})")
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
    "description": "Clock time. Prefer canonical 24-hour HH:MM; Python normalizes valid structured clock forms.",
}
OBJECTIVE = {
    "type": "string",
    "enum": _objective_ids(),
    "description": _objective_description(),
}
SC_COUNT = {"type": "integer", "minimum": 0, "maximum": 4}
METRIC = {
    "type": "string",
    "enum": ["failure_probability", "total_gbps", "blocking", "reconfiguration"],
}
SLA_STATE = {"type": "string", "enum": ["normal", "degraded", "failure_prone"]}


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
            {"time": TIME},
        ),
        _function_tool(
            "get_sla_prediction",
            "Predict SLA state and Failure-prone risk at one timestamp. Use for direct SLA/risk questions that do not ask why/explain a stated claim.",
            {"time": TIME},
        ),
        _function_tool(
            "explain_sla_risk",
            "Explain or correct an SLA-state/risk claim at one timestamp using validated evidence. Use for why/explain/correct-premise questions; do not additionally call get_sla_prediction.",
            {"time": TIME, "claimed_state": SLA_STATE},
        ),
        _function_tool(
            "get_network_state_at_time",
            "Return a complete network-state snapshot at one timestamp: traffic, SLA risk/state and SC allocation/policy state. Do not use for a traffic-only, SLA-only or named-policy counterfactual question.",
            {"time": TIME, "policy": POLICY},
        ),
        _function_tool(
            "compare_policies_at_time",
            "Compare configured policies at one timestamp and choose/recommend according to an optimization objective such as balanced, minimum blocking, minimum reconfiguration, or SLA priority. Optimization preferences are objectives, not hard SC constraints.",
            {"time": TIME, "objective": OBJECTIVE},
        ),
        _function_tool(
            "simulate_policy_at_time",
            "Evaluate the counterfactual outcome of one explicitly named policy at one timestamp. Use when the operator asks how PCA/MBA/SAA would perform or what that named policy would produce.",
            {"time": TIME, "policy": POLICY},
        ),
        _function_tool(
            "analyze_constrained_allocation",
            "Evaluate explicit hard SC-count constraints such as keep RAN on 2 SCs or reserve 1 SC for PON. Do not use merely because the operator wants fewer reconfigurations, lower blocking, or strict service priority; those are optimization objectives.",
            {
                "time": TIME,
                "enterprise_subcarriers": SC_COUNT,
                "ran_subcarriers": SC_COUNT,
                "pon_subcarriers": SC_COUNT,
                "reference_policy": POLICY,
                "objective": OBJECTIVE,
            },
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
