from app import config
from app.agents.tool_catalog import TOOLS, tool_schemas
from app.runtime import MultiAgentRuntime
from app.schemas import ContextInterpretation, CoordinatorDecision


def test_tool_catalog_uses_configured_policies_and_objectives():
    policy_enum = TOOLS["simulate_policy_at_time"]["function"]["parameters"]["properties"]["policy"]["enum"]
    objective_enum = TOOLS["compare_policies_at_time"]["function"]["parameters"]["properties"]["objective"]["enum"]
    assert set(policy_enum) == set(config.policy_ids())
    assert set(objective_enum) == set(config.recommendation_objectives())


def test_inherited_intent_restricts_native_tool_scope_without_language_parsing():
    decision = CoordinatorDecision(
        context=ContextInterpretation(relation="followup", inherit=["intent", "time"]),
        handoffs=[],
    )
    assert MultiAgentRuntime._native_tool_scope(
        decision,
        {"last_tool": "get_traffic_forecast", "last_time": "10:00"},
    ) == ("get_traffic_forecast",)


def test_explicit_intent_change_keeps_full_native_tool_catalog_available():
    decision = CoordinatorDecision(
        context=ContextInterpretation(relation="followup", inherit=["time"]),
        handoffs=[],
    )
    assert MultiAgentRuntime._native_tool_scope(
        decision,
        {"last_tool": "get_traffic_forecast", "last_time": "10:00"},
    ) is None


def test_ollama_tool_schema_is_native_function_format():
    schema = tool_schemas(("get_traffic_forecast",))[0]
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "get_traffic_forecast"
