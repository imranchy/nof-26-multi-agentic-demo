from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LocalAgentSpec:
    name: str
    description: str
    tools: tuple[str, ...]


LOCAL_AGENT_SPECS: dict[str, LocalAgentSpec] = {
    "traffic_agent": LocalAgentSpec(
        name="traffic_agent",
        description="Handles offered-traffic prediction at a timestamp.",
        tools=("get_traffic_forecast",),
    ),
    "sla_agent": LocalAgentSpec(
        name="sla_agent",
        description="Handles SLA-state/risk prediction and correction of SLA-state claims.",
        tools=("get_sla_prediction", "explain_sla_risk"),
    ),
    "policy_agent": LocalAgentSpec(
        name="policy_agent",
        description="Handles policy comparison, objective-aware selection, policy counterfactuals, and explicit SC-allocation constraints.",
        tools=("compare_policies_at_time", "simulate_policy_at_time", "analyze_constrained_allocation"),
    ),
    "network_analysis_agent": LocalAgentSpec(
        name="network_analysis_agent",
        description="Handles full network state, cross-time comparison, ranked interval discovery, and continuous time-range summaries.",
        tools=("get_network_state_at_time", "compare_network_states", "find_risk_intervals", "summarize_time_range"),
    ),
    "scope_agent": LocalAgentSpec(
        name="scope_agent",
        description="Handles physical-layer requests that are intentionally unsupported and generic out-of-scope requests.",
        tools=("decline_physical_layer", "decline_out_of_scope"),
    ),
}

LOCAL_AGENT_NAMES = tuple(LOCAL_AGENT_SPECS)


def agent_catalog() -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "tools": list(spec.tools),
        }
        for spec in LOCAL_AGENT_SPECS.values()
    ]
