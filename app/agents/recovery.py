from __future__ import annotations

import pandas as pd

from itertools import product




class RecoveryAgent:
    """Evaluate the three allocations observed under priority_trf."""

    SC_CAPACITY_GBPS = 25.0

    # Internal machine-readable allocation codes.
    LAYOUTS = {
        "EE|P|R": {
            "enterprise": 2,
            "pon": 1,
            "ran": 1,
        },
        "E|PP|R": {
            "enterprise": 1,
            "pon": 2,
            "ran": 1,
        },
        "E|P|RR": {
            "enterprise": 1,
            "pon": 1,
            "ran": 2,
        },
    }

    def analyze_constraints(
        self,
        row: pd.Series,
        fixed: dict[str, int] | None = None,
        total_subcarriers: int = 4,
    ) -> dict:
        """
        Evaluate operator constraints using only the three allocation
        layouts observed under the NoF priority_trf configuration.
        """
        fixed = fixed or {}
        services = ("enterprise", "pon", "ran")

        if total_subcarriers != 4:
            raise ValueError(
                "The NoF demonstration assumes exactly four subcarriers."
            )

        loads = {
            service: float(row[f"{service}_gbps"])
            for service in services
        }

        candidates = []

        for layout, allocation in self.LAYOUTS.items():

            # Keep only NoF layouts that satisfy the operator constraint.
            if any(
                allocation[service] != count
                for service, count in fixed.items()
            ):
                continue

            overflow = {
                service: max(
                    0.0,
                    loads[service]
                    - allocation[service] * self.SC_CAPACITY_GBPS,
                )
                for service in services
            }

            candidates.append(
                {
                    "layout": layout,
                    "allocation": dict(allocation),
                    "overflow_gbps": overflow,
                    "total_overflow_gbps": sum(
                        overflow.values()
                    ),
                }
            )

        if not candidates:
            return {
                "observed_policy": "priority_trf",
                "constraint_feasible": False,
                "traffic_fully_served": False,
                "operator_constraints": fixed,
                "reason": (
                    "No allocation in the NoF priority_trf layout "
                    "catalogue satisfies the supplied constraints."
                ),
            }

        best = min(
            candidates,
            key=lambda item: item["total_overflow_gbps"],
        )

        total_overflow = best["total_overflow_gbps"]

        return {
            "observed_policy": "priority_trf",
            "layout": best["layout"],
            "allocation": best["allocation"],
            "capacity_gbps": {
                service: (
                    best["allocation"][service]
                    * self.SC_CAPACITY_GBPS
                )
                for service in services
            },
            "overflow_gbps": best["overflow_gbps"],
            "total_overflow_gbps": round(
                total_overflow,
                2,
            ),
            "constraint_feasible": True,
            "traffic_fully_served": (
                total_overflow <= 1e-9
            ),
            "operator_constraints": fixed,
            "evaluated_candidates": len(candidates),
        }






           

    def recommend(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Add allocation recommendations to every forecast interval."""
        df = frame.copy()

        decisions = df.apply(
            self._evaluate_row,
            axis=1,
            result_type="expand",
        )

        for column in decisions.columns:
            df[column] = decisions[column]

        return df

    @staticmethod
    def _describe_allocation(
        allocation: dict[str, int],
    ) -> str:
        """Convert an allocation into an operator-readable description."""
        return (
            f"{allocation['enterprise']} subcarrier"
            f"{'' if allocation['enterprise'] == 1 else 's'} to Enterprise, "
            f"{allocation['pon']} subcarrier"
            f"{'' if allocation['pon'] == 1 else 's'} to PON, and "
            f"{allocation['ran']} subcarrier"
            f"{'' if allocation['ran'] == 1 else 's'} to RAN"
        )

    def _evaluate_row(
        self,
        row: pd.Series,
    ) -> dict:
        """Evaluate all observed allocations for one forecast interval."""
        loads = {
            service: float(row[f"{service}_gbps"])
            for service in (
                "enterprise",
                "pon",
                "ran",
            )
        }

        evaluations = []

        for layout, allocation in self.LAYOUTS.items():
            overflow = {
                service: max(
                    0.0,
                    loads[service]
                    - allocation[service] * self.SC_CAPACITY_GBPS,
                )
                for service in loads
            }

            evaluations.append(
                (
                    sum(overflow.values()),
                    layout,
                    overflow,
                    allocation,
                )
            )

        # Select the allocation with the lowest total predicted overflow.
        total_overflow, layout, overflow, allocation = min(
            evaluations,
            key=lambda item: item[0],
        )

        allocation_description = self._describe_allocation(
            allocation
        )

        affected = [
            service.upper()
            for service, value in overflow.items()
            if value > 1e-9
        ]

        feasible = total_overflow <= 1e-9
        state = row["predicted_state"]

        if state == "normal":
            action = (
                "Continue monitoring; no proactive allocation "
                "change is indicated."
            )
            priority = "none"
            approval = False

        elif feasible:
            action = (
                f"Evaluate allocating {allocation_description}. "
                "This allocation accommodates the predicted service "
                "loads within the four available 25-Gbps subcarriers."
            )
            priority = (
                "medium"
                if state == "degraded"
                else "high"
            )
            approval = True

        else:
            services = ", ".join(affected)

            action = (
                f"Evaluate allocating {allocation_description}. "
                "Even this minimum-overflow allocation leaves an "
                f"estimated {total_overflow:.2f} Gbps unmet for "
                f"{services}; prepare external capacity, traffic "
                "offloading, or rerouting."
            )
            priority = (
                "medium"
                if state == "degraded"
                else "high"
            )
            approval = True

        return {
            # Retain the compact code as structured internal evidence.
            "candidate_layout": layout,

            # Operator-readable allocation information.
            "candidate_enterprise_subcarriers": allocation[
                "enterprise"
            ],
            "candidate_pon_subcarriers": allocation["pon"],
            "candidate_ran_subcarriers": allocation["ran"],
            "candidate_allocation_description": (
                allocation_description
            ),

            # Capacity represented by the suggested allocation.
            "candidate_enterprise_capacity_gbps": (
                allocation["enterprise"]
                * self.SC_CAPACITY_GBPS
            ),
            "candidate_ran_capacity_gbps": (
                allocation["ran"]
                * self.SC_CAPACITY_GBPS
            ),
            "candidate_pon_capacity_gbps": (
                allocation["pon"]
                * self.SC_CAPACITY_GBPS
            ),

            # Feasibility and recovery recommendation.
            "estimated_overflow_gbps": round(
                total_overflow,
                2,
            ),
            "overflow_services": affected,
            "layout_feasible": feasible,
            "recommended_action": action,
            "action_priority": priority,
            "operator_approval_required": approval,
        }