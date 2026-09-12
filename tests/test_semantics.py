from __future__ import annotations

from app.semantic import SemanticResolver


def test_time_value_normalization_is_language_independent_value_validation():
    assert SemanticResolver.normalize_time_value("9:30 PM") == "21:30"
    assert SemanticResolver.normalize_time_value("21:30") == "21:30"


def test_policy_validation_accepts_only_supported_identifiers():
    assert SemanticResolver.normalize_policy("pca") == "PCA"
    assert SemanticResolver.normalize_policy("MBA") == "MBA"
    assert SemanticResolver.normalize_policy("unknown") is None


def test_objective_validation_uses_canonical_enum_only():
    assert SemanticResolver.normalize_objective_value("min_blocking") == "min_blocking"
    assert SemanticResolver.normalize_objective_value("something else", "balanced") == "balanced"


def test_constraint_validation_keeps_only_bounded_structured_counts():
    assert SemanticResolver.normalize_constraints({
        "ran_subcarriers": 2,
        "pon_subcarriers": "1",
        "enterprise_subcarriers": 9,
        "unrelated": 3,
    }) == {
        "ran_subcarriers": 2,
        "pon_subcarriers": 1,
    }


def test_metric_and_top_k_validation():
    assert SemanticResolver.normalize_metric("blocking") == "blocking"
    assert SemanticResolver.normalize_metric("not-a-metric") == "failure_probability"
    assert SemanticResolver.normalize_top_k(12) == 10
    assert SemanticResolver.normalize_top_k(0) == 1
