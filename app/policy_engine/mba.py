from __future__ import annotations

from app.policy_engine.base import AllocationPolicy, IDLE, PolicyContext, SERVICES


class MBAPolicy(AllocationPolicy):
    policy_id = "MBA"

    def allocate(self, demand_gbps, context: PolicyContext, previous_assignment=None):
        residual = {service: max(0.0, float(demand_gbps[service])) for service in SERVICES}
        assignment: list[str] = []
        tie_order = {service: i for i, service in enumerate(context.priority)}
        for _ in range(context.sc_count):
            if max(residual.values(), default=0.0) <= 1e-12:
                assignment.append(IDLE)
                continue
            service = max(
                SERVICES,
                key=lambda s: (context.weights[s] * residual[s], -tie_order[s]),
            )
            assignment.append(service)
            residual[service] = max(0.0, residual[service] - context.sc_capacity_gbps)
        return assignment
