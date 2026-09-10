from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

SERVICES = ("enterprise", "ran", "pon")
IDLE = "idle"
ASSIGNMENT_STATES = SERVICES + (IDLE,)


@dataclass(frozen=True)
class PolicyContext:
    sc_capacity_gbps: float
    sc_count: int
    weights: dict[str, float]
    priority: list[str]
    beta: float


@dataclass
class PolicyResult:
    policy: str
    assignment: list[str]
    demand_gbps: dict[str, float]
    capacity_gbps: dict[str, float]
    served_new_gbps: dict[str, float]
    blocked_new_gbps: dict[str, float]
    overall_blocking_ratio_epoch: float
    blocking_event: int
    per_class_blocking_ratio: dict[str, float]
    fresh_service_ratio: float
    reconfig_event: int
    reconfig_count: int
    weighted_reconfig_cost: float
    backlog_pressure_ratio: float | None = None
    backlog_recovery_ratio: float | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["allocation_counts"] = {
            state: self.assignment.count(state) for state in ASSIGNMENT_STATES
        }
        value["assignment_label"] = " | ".join(state.upper() for state in self.assignment)
        value["active_subcarriers"] = sum(1 for state in self.assignment if state != IDLE)
        value["idle_subcarriers"] = self.assignment.count(IDLE)
        return value


class AllocationPolicy(ABC):
    policy_id: str

    @abstractmethod
    def allocate(
        self,
        demand_gbps: dict[str, float],
        context: PolicyContext,
        previous_assignment: list[str] | None = None,
    ) -> list[str]:
        raise NotImplementedError
