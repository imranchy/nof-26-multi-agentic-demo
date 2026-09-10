from __future__ import annotations

import math

from app.policy_engine.base import AllocationPolicy, IDLE, PolicyContext


class PCAPolicy(AllocationPolicy):
    policy_id = "PCA"

    def allocate(self, demand_gbps, context: PolicyContext, previous_assignment=None):
        assignment: list[str] = []
        remaining = context.sc_count
        for service in context.priority:
            if remaining <= 0:
                break
            needed = int(math.ceil(max(0.0, float(demand_gbps[service])) / context.sc_capacity_gbps))
            count = min(needed, remaining)
            assignment.extend([service] * count)
            remaining -= count
        # Operator-facing extension: capacity not required to serve any residual
        # demand is represented explicitly as IDLE rather than inventing a class
        # allocation. This does not change served traffic or blocking.
        assignment.extend([IDLE] * remaining)
        return assignment
