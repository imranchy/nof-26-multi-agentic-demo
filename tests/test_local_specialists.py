import json

from app.agents.specialist import LocalSpecialistAgent


def test_native_tool_call_accepts_allowed_function():
    name, args = LocalSpecialistAgent._validate_native_tool_calls(
        [{"type": "function", "function": {"name": "get_traffic_forecast", "arguments": {"time": "09:00"}}}],
        ("get_traffic_forecast",),
    )
    assert name == "get_traffic_forecast"
    assert args == {"time": "09:00"}


def test_native_tool_call_rejects_unavailable_function():
    try:
        LocalSpecialistAgent._validate_native_tool_calls(
            [{"type": "function", "function": {"name": "simulate_policy_at_time", "arguments": {"policy": "PCA"}}}],
            ("get_traffic_forecast",),
        )
    except ValueError as exc:
        assert "not available" in str(exc)
    else:
        raise AssertionError("unavailable function should be rejected")


def test_native_tool_call_requires_exactly_one_function():
    try:
        LocalSpecialistAgent._validate_native_tool_calls([], ("get_traffic_forecast",))
    except ValueError as exc:
        assert "exactly one" in str(exc)
    else:
        raise AssertionError("missing native tool call should be rejected")


def test_native_tool_call_accepts_json_string_arguments():
    name, args = LocalSpecialistAgent._validate_native_tool_calls(
        [{"function": {"name": "analyze_constrained_allocation", "arguments": json.dumps({"pon_subcarriers": 1})}}],
        ("analyze_constrained_allocation",),
    )
    assert name == "analyze_constrained_allocation"
    assert args == {"pon_subcarriers": 1}
