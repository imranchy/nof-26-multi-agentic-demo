from __future__ import annotations

from app.policy_engine.base import IDLE, PolicyResult, SERVICES


def compute_policy_result(
    policy: str,
    assignment: list[str],
    demand_gbps: dict[str, float],
    sc_capacity_gbps: float,
    previous_assignment: list[str] | None = None,
    weights: dict[str, float] | None = None,
) -> PolicyResult:
    weights = weights or {service: 1.0 for service in SERVICES}
    capacity = {service: assignment.count(service) * sc_capacity_gbps for service in SERVICES}
    served = {service: min(float(demand_gbps[service]), capacity[service]) for service in SERVICES}
    blocked = {service: max(0.0, float(demand_gbps[service]) - served[service]) for service in SERVICES}
    total_offered = sum(float(demand_gbps[s]) for s in SERVICES)
    total_served = sum(served.values())
    total_blocked = sum(blocked.values())
    blocking_ratio = total_blocked / total_offered if total_offered > 0 else 0.0
    per_class = {
        service: blocked[service] / float(demand_gbps[service]) if float(demand_gbps[service]) > 0 else 0.0
        for service in SERVICES
    }

    if previous_assignment is None:
        reconfig_count = 0
        weighted_cost = 0.0
    else:
        if len(previous_assignment) != len(assignment):
            raise ValueError("Previous and current assignments must have equal length")
        changes = [(old, new) for old, new in zip(previous_assignment, assignment) if old != new]
        reconfig_count = len(changes)
        def w(state: str) -> float:
            return 0.0 if state == IDLE else float(weights.get(state, 1.0))
        weighted_cost = sum((w(old) + w(new)) / 2 for old, new in changes)

    return PolicyResult(
        policy=policy,
        assignment=list(assignment),
        demand_gbps={k: round(float(v), 6) for k, v in demand_gbps.items()},
        capacity_gbps={k: round(v, 6) for k, v in capacity.items()},
        served_new_gbps={k: round(v, 6) for k, v in served.items()},
        blocked_new_gbps={k: round(v, 6) for k, v in blocked.items()},
        overall_blocking_ratio_epoch=round(blocking_ratio, 8),
        blocking_event=int(total_blocked > 1e-9),
        per_class_blocking_ratio={k: round(v, 8) for k, v in per_class.items()},
        fresh_service_ratio=round(total_served / total_offered, 8) if total_offered > 0 else 1.0,
        reconfig_event=int(reconfig_count > 0),
        reconfig_count=reconfig_count,
        weighted_reconfig_cost=round(weighted_cost, 6),
        backlog_pressure_ratio=None,
        backlog_recovery_ratio=None,
    )
