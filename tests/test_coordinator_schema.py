from app.agents.coordinator import CoordinatorAgent


def test_valid_relative_context_handoff_decision():
    decision = CoordinatorAgent._validate_decision({
        "context": {
            "relation": "followup",
            "inherit": ["intent", "time"],
            "relative_time": {"offset_minutes": 60},
        },
        "handoffs": ["traffic_agent"],
    })
    assert decision.context.relation == "followup"
    assert decision.context.inherit == ["intent", "time"]
    assert decision.context.relative_time_offset_minutes == 60
    assert decision.handoffs == ["traffic_agent"]


def test_standalone_context_cannot_inherit_even_if_model_attempts_it():
    decision = CoordinatorAgent._validate_decision({
        "context": {"relation": "standalone", "inherit": ["time", "policy"]},
        "handoffs": ["policy_agent"],
    })
    assert decision.context.inherit == []
    assert decision.context.relative_time_offset_minutes is None


def test_relative_time_requires_time_inheritance():
    try:
        CoordinatorAgent._validate_decision({
            "context": {
                "relation": "followup",
                "inherit": ["intent"],
                "relative_time": {"offset_minutes": 60},
            },
            "handoffs": ["traffic_agent"],
        })
    except ValueError as exc:
        assert "requires inherited time" in str(exc)
    else:
        raise AssertionError("invalid context should be rejected")


def test_unknown_handoff_is_rejected():
    try:
        CoordinatorAgent._validate_decision({
            "context": {"relation": "standalone", "inherit": []},
            "handoffs": ["invented_agent"],
        })
    except ValueError as exc:
        assert "unknown specialist handoff" in str(exc)
    else:
        raise AssertionError("unknown handoff should be rejected")
