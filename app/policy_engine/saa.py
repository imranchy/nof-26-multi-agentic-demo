from __future__ import annotations

from app.policy_engine.base import AllocationPolicy, IDLE, PolicyContext, SERVICES


class SAAPolicy(AllocationPolicy):
    policy_id = "SAA"

    def allocate(self, demand_gbps, context: PolicyContext, previous_assignment=None):
        # With no prior state, SAA reduces to MBA as in the PSC formulation.
        if previous_assignment is None:
            from app.policy_engine.mba import MBAPolicy
            return MBAPolicy().allocate(demand_gbps, context)

        residual = {service: max(0.0, float(demand_gbps[service])) for service in SERVICES}
        assignment: list[str] = []
        tie_order = {service: i for i, service in enumerate(context.priority)}
        for sc_index in range(context.sc_count):
            if max(residual.values(), default=0.0) <= 1e-12:
                assignment.append(IDLE)
                continue
            previous = previous_assignment[sc_index]
            service = max(
                SERVICES,
                key=lambda s: (
                    context.weights[s] * residual[s] - (context.beta if s != previous else 0.0),
                    int(s == previous),
                    -tie_order[s],
                ),
            )
            assignment.append(service)
            residual[service] = max(0.0, residual[service] - context.sc_capacity_gbps)
        return assignment
