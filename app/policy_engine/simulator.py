from __future__ import annotations

from itertools import product
from typing import Any

import pandas as pd

from app.policy_engine.base import ASSIGNMENT_STATES, SERVICES
from app.policy_engine.metrics import compute_policy_result
from app.policy_engine.registry import PolicyRegistry


class PolicySimulator:
    def __init__(self, forecast_frame: pd.DataFrame, registry: PolicyRegistry | None = None) -> None:
        self.frame = forecast_frame.sort_values("minute_of_day").reset_index(drop=True).copy()
        self.registry = registry or PolicyRegistry.load()
        self._traces: dict[str, list[dict[str, Any]]] = {}

    def replay(self, policy_id: str) -> list[dict[str, Any]]:
        policy_id = policy_id.upper()
        if policy_id in self._traces:
            return self._traces[policy_id]
        policy = self.registry.get(policy_id)
        previous: list[str] | None = None
        trace: list[dict[str, Any]] = []
        for _, row in self.frame.iterrows():
            demand = {service: float(row[f"{service}_gbps"]) for service in SERVICES}
            assignment = policy.allocate(demand, self.registry.context, previous)
            result = compute_policy_result(
                policy_id,
                assignment,
                demand,
                self.registry.context.sc_capacity_gbps,
                previous_assignment=previous,
                weights=self.registry.context.weights,
            )
            item = result.to_dict()
            item["time"] = str(row["time"])
            item["minute_of_day"] = int(row["minute_of_day"])
            trace.append(item)
            previous = assignment
        self._traces[policy_id] = trace
        return trace

    def at_time(self, policy_id: str, time_value: str) -> dict[str, Any]:
        minute = self._parse_time(time_value)
        for item in self.replay(policy_id):
            if item["minute_of_day"] == minute:
                return item
        raise ValueError(f"Timestamp {time_value} is not present in the 5-minute forecast grid.")

    def previous_assignment(self, policy_id: str, time_value: str) -> list[str] | None:
        minute = self._parse_time(time_value)
        trace = self.replay(policy_id)
        for index, item in enumerate(trace):
            if item["minute_of_day"] == minute:
                return None if index == 0 else list(trace[index - 1]["assignment"])
        raise ValueError(f"Timestamp {time_value} is not present in the forecast grid.")

    def constrained(
        self,
        time_value: str,
        fixed_counts: dict[str, int],
        reference_policy: str = "SAA",
        objective: str = "balanced",
        blocking_tolerance_ratio: float = 0.005,
    ) -> dict[str, Any]:
        minute = self._parse_time(time_value)
        row = self.frame.loc[self.frame["minute_of_day"] == minute]
        if row.empty:
            raise ValueError(f"Timestamp {time_value} is not present in the forecast grid.")
        row = row.iloc[0]
        demand = {service: float(row[f"{service}_gbps"]) for service in SERVICES}
        for service, count in fixed_counts.items():
            if service not in SERVICES:
                raise ValueError(f"Unknown service constraint: {service}")
            if not 0 <= int(count) <= self.registry.context.sc_count:
                raise ValueError(f"SC count for {service} must be between 0 and {self.registry.context.sc_count}")
        if sum(int(v) for v in fixed_counts.values()) > self.registry.context.sc_count:
            return {"constraint_feasible": False, "reason": "Operator constraints require more SCs than are available."}

        previous = self.previous_assignment(reference_policy, time_value)
        candidates: list[dict[str, Any]] = []
        for assignment_tuple in product(ASSIGNMENT_STATES, repeat=self.registry.context.sc_count):
            assignment = list(assignment_tuple)
            counts = {service: assignment.count(service) for service in SERVICES}
            if any(counts[service] != int(value) for service, value in fixed_counts.items()):
                continue
            result = compute_policy_result(
                "OPERATOR_CONSTRAINED",
                assignment,
                demand,
                self.registry.context.sc_capacity_gbps,
                previous_assignment=previous,
                weights=self.registry.context.weights,
            ).to_dict()
            candidates.append(result)
        if not candidates:
            return {"constraint_feasible": False, "reason": "No four-SC assignment satisfies the operator constraints."}

        if objective == "min_reconfiguration":
            best = min(candidates, key=lambda x: (x["reconfig_count"], x["overall_blocking_ratio_epoch"], x["assignment_label"]))
        else:
            min_block = min(x["overall_blocking_ratio_epoch"] for x in candidates)
            tolerance = 0.0 if objective == "min_blocking" else blocking_tolerance_ratio
            near = [x for x in candidates if x["overall_blocking_ratio_epoch"] <= min_block + tolerance + 1e-12]
            best = min(near, key=lambda x: (x["reconfig_count"], x["weighted_reconfig_cost"], x["assignment_label"]))
        return {
            "constraint_feasible": True,
            "traffic_fully_served": best["overall_blocking_ratio_epoch"] <= 1e-12,
            "operator_constraints": {k: int(v) for k, v in fixed_counts.items()},
            "reference_policy": reference_policy.upper(),
            "objective": objective,
            "evaluated_assignments": len(candidates),
            "result": best,
        }

    @staticmethod
    def _parse_time(value: str) -> int:
        text = str(value).strip()
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError("Time must use HH:MM format.")
        hour, minute = int(parts[0]), int(parts[1])
        if hour not in range(24) or minute not in range(60):
            raise ValueError("Time must be a valid 24-hour HH:MM value.")
        if minute % 5 != 0:
            raise ValueError("The forecast uses 5-minute timestamps; minute must be divisible by 5.")
        return hour * 60 + minute
