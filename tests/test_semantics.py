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
