from __future__ import annotations

from app.policy_engine.metrics import compute_policy_result
from app.policy_engine.registry import PolicyRegistry


def test_pca_matches_fixed_priority_semantics():
    registry = PolicyRegistry.load()
    assignment = registry.get("PCA").allocate(
        {"enterprise": 30.0, "ran": 40.0, "pon": 20.0}, registry.context
    )
    assert assignment == ["enterprise", "enterprise", "ran", "ran"]


def test_mba_uses_weighted_residual_demand():
    registry = PolicyRegistry.load()
    assignment = registry.get("MBA").allocate(
        {"enterprise": 30.0, "ran": 40.0, "pon": 20.0}, registry.context
    )
    assert assignment == ["ran", "enterprise", "ran", "pon"]


def test_saa_reduces_to_mba_without_previous_assignment():
    registry = PolicyRegistry.load()
    demand = {"enterprise": 30.0, "ran": 40.0, "pon": 20.0}
    assert registry.get("SAA").allocate(demand, registry.context, None) == registry.get("MBA").allocate(demand, registry.context, None)


def test_policy_metrics_conserve_traffic_and_reconfigurations():
    result = compute_policy_result(
        "TEST",
        ["ran", "enterprise", "ran", "pon"],
        {"enterprise": 30.0, "ran": 40.0, "pon": 20.0},
        25.0,
        previous_assignment=["enterprise", "enterprise", "ran", "pon"],
        weights={"enterprise": 1.3, "ran": 1.1, "pon": 0.7},
    )
    assert result.reconfig_count == 1
    assert result.blocked_new_gbps == {"enterprise": 5.0, "ran": 0.0, "pon": 0.0}
    assert abs(result.fresh_service_ratio - 85.0 / 90.0) < 1e-8
    for service in ("enterprise", "ran", "pon"):
        assert abs(result.served_new_gbps[service] + result.blocked_new_gbps[service] - result.demand_gbps[service]) < 1e-9


def test_low_demand_uses_idle_capacity_instead_of_fake_class_assignment():
    registry = PolicyRegistry.load()
    demand = {"enterprise": 4.0, "ran": 10.0, "pon": 8.0}
    assignment = registry.get("MBA").allocate(demand, registry.context)
    assert assignment.count("idle") == 1
    assert len(assignment) == 4
