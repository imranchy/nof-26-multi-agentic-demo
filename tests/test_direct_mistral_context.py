import json

from app.agents.specialist import LocalSpecialistAgent


def test_native_ollama_tool_protocol_parses_direct_function_call():
    name, args = LocalSpecialistAgent._validate_native_tool_calls(
        [
            {
                "type": "function",
                "function": {
                    "name": "get_traffic_forecast",
                    "arguments": {"time": "21:15"},
                },
            }
        ],
        ("get_traffic_forecast",),
    )
    assert name == "get_traffic_forecast"
    assert args == {"time": "21:15"}


def test_native_ollama_tool_protocol_accepts_string_arguments():
    payload = json.dumps({"time": "21:15"})
    name, args = LocalSpecialistAgent._validate_native_tool_calls(
        [
            {
                "function": {
                    "name": "get_traffic_forecast",
                    "arguments": payload,
                }
            }
        ],
        ("get_traffic_forecast",),
    )
    assert name == "get_traffic_forecast"
    assert args == {"time": "21:15"}
