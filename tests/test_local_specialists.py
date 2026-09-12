from app.agents.specialist import LocalSpecialistAgent


def test_traffic_specialist_can_only_emit_traffic_tool():
    steps = LocalSpecialistAgent._validate_steps(
        "traffic_agent",
        {"steps": [{"name": "get_traffic_forecast", "arguments": {"time": "09:00"}}]},
    )
    assert steps == [("get_traffic_forecast", {"time": "09:00"})]


def test_specialist_cannot_cross_handoff_boundary():
    try:
        LocalSpecialistAgent._validate_steps(
            "traffic_agent",
            {"steps": [{"name": "simulate_policy_at_time", "arguments": {"policy": "PCA"}}]},
        )
    except ValueError as exc:
        assert "cannot call" in str(exc)
    else:
        raise AssertionError("cross-agent tool use should be rejected")


def test_policy_specialist_accepts_constraint_tool():
    steps = LocalSpecialistAgent._validate_steps(
        "policy_agent",
        {"steps": [{"name": "analyze_constrained_allocation", "arguments": {"pon_subcarriers": 1}}]},
    )
    assert steps[0][0] == "analyze_constrained_allocation"
