from __future__ import annotations

from app.agents.guardrail import GuardrailAgent


def test_grounded_numeric_answer_passes():
    guard = GuardrailAgent()
    evidence = {"timestamp": "21:15", "value": 5.27, "count": 0}
    passed, issues = guard.validate_answer("At 21:15 the value is 5.27 with 0 changes.", evidence)
    assert passed
    assert not issues


def test_hallucinated_number_is_rejected():
    guard = GuardrailAgent()
    passed, issues = guard.validate_answer("The blocking is 7.91%.", {"blocking_percent": 5.27})
    assert not passed
    assert "unsupported_numeric_claim" in issues


def test_physical_layer_claim_is_rejected():
    guard = GuardrailAgent()
    passed, issues = guard.validate_answer("This is caused by a fiber cut.", {})
    assert not passed
    assert "unsupported_physical_layer_diagnosis" in issues


def test_wrong_sla_state_claim_is_rejected_categorically():
    guard = GuardrailAgent()
    evidence = {"sla": {"state": "normal"}}
    passed, issues = guard.validate_answer("The predicted SLA state is failure-prone.", evidence)
    assert not passed
    assert "unsupported_sla_state_claim" in issues


def test_false_recommendation_change_claim_is_rejected():
    guard = GuardrailAgent()
    evidence = {"changed": False, "recommended_at_a": "SAA", "recommended_at_b": "SAA"}
    passed, issues = guard.validate_answer("The recommendation changes from SAA to MBA.", evidence)
    assert not passed
    assert "false_change_claim" in issues or "unsupported_recommendation_claim" in issues


def test_model_names_are_hidden_in_normal_operator_answers():
    guard = GuardrailAgent()
    evidence = {"category": "sla_prediction", "sla": {"state": "normal", "failure_prone_probability": 0.12}}
    passed, issues = guard.validate_answer("The Random Forest predicts normal with 12% risk.", evidence, query="What is the SLA state?")
    assert not passed
    assert "implementation_detail_exposed" in issues


def test_causal_sla_claim_is_rejected_without_attribution():
    guard = GuardrailAgent()
    evidence = {"category": "sla_risk_explanation", "sla": {"state": "normal", "failure_prone_probability": 0.12}, "causal_attribution_available": False}
    passed, issues = guard.validate_answer("The risk is due to PON traffic.", evidence, query="Explain the risk")
    assert not passed
    assert "unsupported_causal_claim" in issues
