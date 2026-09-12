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


def test_select_tool_reads_ollama_native_tool_calls(monkeypatch):
    import json

    from app.agents import specialist as specialist_module

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "get_traffic_forecast",
                                "arguments": {"time": "21:15"},
                            },
                        }
                    ],
                }
            }).encode("utf-8")

    monkeypatch.setattr(specialist_module, "urlopen", lambda request, timeout=90: FakeResponse())

    agent = LocalSpecialistAgent(use_llm=True)
    name, args = agent.select_tool(
        query="What traffic do you expect at 21:15?",
        context_memory={},
        conversation_history=[],
        allowed_tools_override=("get_traffic_forecast",),
    )

    assert name == "get_traffic_forecast"
    assert args == {"time": "21:15"}
    assert agent.last_audit["mode"] == "ollama_native_tool_calling"
    assert agent.last_audit["parse_failed"] is False
