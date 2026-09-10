from __future__ import annotations

from app.semantic import SemanticResolver


def test_vague_best_defaults_to_balanced():
    assert SemanticResolver.normalize_objective("Which policy is preferable?", "min_blocking") == "balanced"


def test_minimize_blocking_maps_to_min_blocking():
    assert SemanticResolver.normalize_objective("Minimize blocking at 21:15", "balanced") == "min_blocking"


def test_stability_language_maps_to_min_reconfiguration():
    assert SemanticResolver.normalize_objective("Keep it stable and avoid unnecessary reconfiguration", "balanced") == "min_reconfiguration"


def test_ran_constraint_is_extracted():
    assert SemanticResolver.extract_constraints("Keep RAN on 2 subcarriers") == {"ran_subcarriers": 2}


def test_two_explicit_times_are_parsed():
    assert SemanticResolver.explicit_times("Compare 18:10 with 21:15") == ["18:10", "21:15"]


def test_relative_hour_followup():
    assert SemanticResolver.normalize_time("What about an hour later?", None, {"last_time": "18:10"}) == "19:10"


def test_sla_false_premise_routes_to_sla_explanation():
    assert SemanticResolver.high_confidence_tool("Why is 00:00 classified as failure-prone?", {}) == "explain_sla_risk"


def test_sc_constraint_forces_constraint_capability():
    assert SemanticResolver.high_confidence_tool("Keep RAN on 2 subcarriers at 21:15", {}) == "analyze_constrained_allocation"


def test_temporal_comparison_is_protected():
    assert SemanticResolver.high_confidence_tool("Compare the network at 18:10 and 21:15", {}) == "compare_network_states"


def test_generic_out_of_scope_is_not_sent_to_time_parser():
    assert SemanticResolver.high_confidence_tool("Write me a birthday poem", {"last_tool": "get_network_state_at_time"}) == "decline_out_of_scope"


def test_policy_is_extracted():
    assert SemanticResolver.extract_policy("Use PCA instead") == "PCA"


def test_relative_followup_preserves_previous_capability():
    assert SemanticResolver.high_confidence_tool("What about an hour later?", {"last_tool": "get_network_state_at_time"}) == "get_network_state_at_time"


def test_avoid_unnecessary_sc_changes_maps_to_min_reconfiguration():
    assert SemanticResolver.normalize_objective(
        "At 16:20, avoid unnecessary SC changes above everything else.",
        "balanced",
    ) == "min_reconfiguration"


def test_strict_service_priority_routes_to_policy_comparison():
    assert SemanticResolver.high_confidence_tool(
        "At 23:10, preserve strict service priority when choosing the policy.",
        {},
    ) == "compare_policies_at_time"


def test_traffic_outlook_routes_to_traffic_forecast():
    assert SemanticResolver.high_confidence_tool(
        "Traffic outlook, 05:55.",
        {},
    ) == "get_traffic_forecast"


def test_busy_expected_services_routes_to_traffic_forecast():
    assert SemanticResolver.high_confidence_tool(
        "How busy do you expect Enterprise, RAN and PON to be at 12:35?",
        {},
    ) == "get_traffic_forecast"


def test_operator_snapshot_routes_to_network_state():
    assert SemanticResolver.high_confidence_tool(
        "Operator snapshot, 12:35.",
        {},
    ) == "get_network_state_at_time"


def test_multicomponent_snapshot_precedes_single_sla_route():
    assert SemanticResolver.high_confidence_tool(
        "At 07:45, show traffic, SLA risk and the SC allocation state.",
        {},
    ) == "get_network_state_at_time"


def test_neutral_between_blocking_and_stability_maps_to_balanced():
    assert SemanticResolver.normalize_objective(
        "Choose between PCA, MBA and SAA without favoring blocking or stability.",
        "min_blocking",
    ) == "balanced"


def test_multiple_named_policies_with_choose_routes_to_comparison():
    assert SemanticResolver.high_confidence_tool(
        "At 20:00, choose between PCA, MBA and SAA without favoring blocking or stability.",
        {},
    ) == "compare_policies_at_time"


def test_few_controller_changes_maps_to_min_reconfiguration():
    assert SemanticResolver.normalize_objective(
        "I want the most stable policy with as few controller changes as possible.",
        "balanced",
    ) == "min_reconfiguration"


def test_named_policy_perform_language_is_counterfactual():
    assert SemanticResolver.high_confidence_tool(
        "How would MBA perform at 18:10?",
        {},
    ) == "simulate_policy_at_time"


def test_named_policy_would_produce_language_is_counterfactual():
    assert SemanticResolver.high_confidence_tool(
        "At 09:30, show me what SAA would produce.",
        {},
    ) == "simulate_policy_at_time"


def test_one_hour_later_followup_preserves_previous_capability():
    assert SemanticResolver.high_confidence_tool(
        "And one hour later?",
        {"last_tool": "get_traffic_forecast", "last_time": "09:00"},
    ) == "get_traffic_forecast"
