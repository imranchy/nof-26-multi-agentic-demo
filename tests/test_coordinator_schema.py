from app.agents.coordinator import CoordinatorAgent


def test_valid_relative_context_decision():
    decision = CoordinatorAgent._validate_decision({
        "context": {
            "relation": "followup",
            "inherit": ["intent", "time"],
            "relative_time": {"offset_minutes": 60},
        },
    })
    assert decision.context.relation == "followup"
    assert decision.context.inherit == ["intent", "time"]
    assert decision.context.relative_time_offset_minutes == 60
    assert decision.handoffs == []


def test_standalone_context_cannot_inherit_even_if_model_attempts_it():
    decision = CoordinatorAgent._validate_decision({
        "context": {"relation": "standalone", "inherit": ["time", "policy"]},
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
        })
    except ValueError as exc:
        assert "requires inherited time" in str(exc)
    else:
        raise AssertionError("invalid context should be rejected")


def test_context_schema_does_not_contain_tool_handoffs():
    schema = CoordinatorAgent._output_schema()
    assert set(schema["properties"]) == {"context"}
