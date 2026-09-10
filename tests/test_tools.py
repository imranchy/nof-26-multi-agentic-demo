from __future__ import annotations

from app.runtime import MultiAgentRuntime


def runtime():
    return MultiAgentRuntime(forecast_mode="prepared", use_llm=False)


def test_timestamped_state_uses_real_policy_engine():
    r = runtime()
    evidence, _ = r.execute_tool_direct("get_network_state_at_time", {"time": "21:15"})
    assert evidence["timestamp"] == "21:15"
    assert evidence["displayed_policy"] == "SAA"
    assert sum(evidence["policy_state"]["allocation_counts"].values()) == 4
    assert evidence["sla"]["state"] in {"normal", "degraded", "failure_prone"}
    assert 0.0 <= evidence["sla"]["failure_prone_probability"] <= 1.0


def test_ml_tools_are_explicit_and_queryable():
    r = runtime()
    forecast, _ = r.execute_tool_direct("get_traffic_forecast", {"time": "21:15"})
    sla, _ = r.execute_tool_direct("get_sla_prediction", {"time": "21:15"})
    assert forecast["category"] == "traffic_forecast"
    assert forecast["traffic"]["total_gbps"] > 0
    assert sla["category"] == "sla_prediction"
    assert 0.0 <= sla["sla"]["failure_prone_probability"] <= 1.0
    assert abs(sum(sla["sla"]["internal_probabilities"].values()) - 1.0) < 1e-3


def test_policy_comparison_contains_three_psc_policies():
    r = runtime()
    evidence, _ = r.execute_tool_direct("compare_policies_at_time", {"time": "21:15", "objective": "balanced"})
    assert set(evidence["policy_results"]) == {"PCA", "MBA", "SAA"}
    assert evidence["recommended_policy"] in evidence["policy_results"]
    assert evidence["policy_results"]["SAA"]["overall_blocking_ratio_epoch"] <= evidence["policy_results"]["PCA"]["overall_blocking_ratio_epoch"]


def test_constrained_allocation_respects_operator_constraint():
    r = runtime()
    evidence, _ = r.execute_tool_direct("analyze_constrained_allocation", {"time": "21:15", "ran_subcarriers": 2})
    assert evidence["constraint_feasible"]
    result = evidence["result"]
    assert result["allocation_counts"]["ran"] == 2
    assert sum(result["allocation_counts"].values()) == 4


def test_cross_timestamp_comparison():
    r = runtime()
    evidence, _ = r.execute_tool_direct("compare_network_states", {"time_a": "18:10", "time_b": "21:15", "policy": "SAA"})
    assert evidence["time_a"] == "18:10"
    assert evidence["time_b"] == "21:15"
    assert "failure_prone_probability" in evidence["delta_b_minus_a"]


def test_range_and_risk_tools():
    r = runtime()
    risk, _ = r.execute_tool_direct("find_risk_intervals", {"metric": "failure_probability", "top_k": 3})
    assert len(risk["intervals"]) == 3
    summary, _ = r.execute_tool_direct("summarize_time_range", {"start_time": "18:00", "end_time": "22:00", "policy": "SAA"})
    assert summary["summary"]["interval_count"] > 0


def test_validation_recomputes_policy():
    r = runtime()
    evidence, _ = r.execute_tool_direct("validate_recommendation", {"time": "21:15", "policy": "SAA"})
    assert evidence["all_policy_checks_passed"]
    assert all(evidence["deterministic_checks"].values())
    assert evidence["trust_boundary"]["mistral_calculates_network_values"] is False


def test_backlog_metrics_are_not_fabricated():
    r = runtime()
    evidence, _ = r.execute_tool_direct("simulate_policy_at_time", {"time": "21:15", "policy": "SAA"})
    assert evidence["simulated_result"]["backlog_pressure_ratio"] is None
    assert evidence["simulated_result"]["backlog_recovery_ratio"] is None


def test_validation_can_target_previous_constrained_result():
    r = runtime()
    args = {"time": "21:15", "ran_subcarriers": 2, "objective": "balanced", "reference_policy": "SAA"}
    evidence, _ = r.execute_tool_direct("analyze_constrained_allocation", args)
    r._update_memory("analyze_constrained_allocation", args, evidence)
    validation, _ = r.execute_tool_direct("validate_recommendation", {"time": "21:15", "target": "last_result"})
    assert validation["validation_target"] == "operator_constrained_allocation"
    assert validation["all_policy_checks_passed"]


def test_evidence_coverage_does_not_claim_calibrated_confidence():
    r = runtime()
    evidence, _ = r.execute_tool_direct("get_evidence_confidence", {"time": "21:15", "policy": "SAA"})
    assert evidence["evidence_layers"]["physical_layer_telemetry"] is False
    assert "not a calibrated probability" in evidence["meaning"]


def test_live_forecast_model_loads_and_produces_complete_day():
    from app.agents.forecast import ForecastAgent
    live = ForecastAgent(mode="live").forecast()
    assert len(live) == 288
    assert live[["enterprise_gbps", "ran_gbps", "pon_gbps", "total_gbps"]].notna().all().all()
    assert (live[["enterprise_gbps", "ran_gbps", "pon_gbps", "total_gbps"]] >= 0).all().all()


def test_false_sla_premise_is_corrected_by_evidence():
    r = runtime()
    evidence, fallback = r.execute_tool_direct("explain_sla_risk", {"time": "00:00", "claimed_state": "failure_prone"})
    assert evidence["premise_matches_prediction"] is False
    assert evidence["sla"]["state"] == "normal"
    assert "premise does not match" in fallback.lower()


def test_range_summary_is_not_just_endpoint_delta():
    r = runtime()
    evidence, _ = r.execute_tool_direct("summarize_time_range", {"start_time": "18:00", "end_time": "22:00"})
    summary = evidence["summary"]
    assert summary["interval_count"] == 49
    assert "peak_load_time" in summary
    assert "highest_risk_time" in summary
    assert set(summary["policy_summaries"]) == {"PCA", "MBA", "SAA"}
    assert set(summary["recommendation_counts"]) == {"PCA", "MBA", "SAA"}


def test_recommendation_change_tool_corrects_false_change_premise():
    r = runtime()
    evidence, fallback = r.execute_tool_direct("explain_recommendation_change", {"time_a": "18:10", "time_b": "21:15", "objective": "balanced"})
    assert evidence["changed"] is False
    assert "does not change" in fallback.lower()


def test_operator_fallbacks_are_model_agnostic():
    r = runtime()
    _, traffic_text = r.execute_tool_direct("get_traffic_forecast", {"time": "21:15"})
    _, sla_text = r.execute_tool_direct("get_sla_prediction", {"time": "21:15"})
    assert "xgboost" not in traffic_text.lower()
    assert "random forest" not in sla_text.lower()
    assert "classifier confidence" not in sla_text.lower()
