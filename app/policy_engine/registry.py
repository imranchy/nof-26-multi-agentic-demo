from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app import config
from app.policy_engine.base import AllocationPolicy, PolicyContext
from app.policy_engine.mba import MBAPolicy
from app.policy_engine.pca import PCAPolicy
from app.policy_engine.saa import SAAPolicy


@dataclass
class PolicyRegistry:
    policies: dict[str, AllocationPolicy]
    metadata: dict[str, dict[str, Any]]
    context: PolicyContext

    @classmethod
    def load(cls) -> "PolicyRegistry":
        network = config.network_parameters()
        sla = config.load_yaml("sla.yaml")
        capacity = float(network["subcarrier_capacity_gbps"])
        beta = float(sla["saa"]["beta_fraction_of_sc_capacity"]) * capacity
        context = PolicyContext(
            sc_capacity_gbps=capacity,
            sc_count=int(network["subcarriers_per_leaf"]),
            weights=config.service_weights(),
            priority=config.service_priority(),
            beta=beta,
        )
        implementations: dict[str, AllocationPolicy] = {
            "PCA": PCAPolicy(),
            "MBA": MBAPolicy(),
            "SAA": SAAPolicy(),
        }
        metadata = {pid: config.load_policy_yaml(pid) for pid in implementations}
        return cls(implementations, metadata, context)

    def get(self, policy_id: str) -> AllocationPolicy:
        key = str(policy_id).upper()
        if key not in self.policies:
            raise ValueError(f"Unknown policy {policy_id}. Expected PCA, MBA, or SAA.")
        return self.policies[key]
