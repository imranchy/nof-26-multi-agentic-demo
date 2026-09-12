from app import config
from app.agents.tool_catalog import ALL_TOOL_NAMES, TOOLS, tool_schemas
from app.runtime import MultiAgentRuntime


def test_tool_catalog_uses_configured_policies_and_objectives():
    policy_enum = TOOLS["simulate_policy_at_time"]["function"]["parameters"]["properties"]["policy"]["enum"]
    objective_enum = TOOLS["compare_policies_at_time"]["function"]["parameters"]["properties"]["objective"]["enum"]
    assert set(policy_enum) == set(config.policy_ids())
    assert set(objective_enum) == set(config.recommendation_objectives())


def test_single_time_tools_expose_structured_relative_offset_for_python_arithmetic():
    props = TOOLS["get_traffic_forecast"]["function"]["parameters"]["properties"]
    assert "time" in props
    assert "relative_time_offset_minutes" in props


def test_full_tool_catalog_is_available_without_coordinator_scope():
    assert "get_traffic_forecast" in ALL_TOOL_NAMES
    assert "get_sla_prediction" in ALL_TOOL_NAMES
    assert "compare_policies_at_time" in ALL_TOOL_NAMES
    assert "simulate_policy_at_time" in ALL_TOOL_NAMES
    assert "request_clarification" in ALL_TOOL_NAMES


def test_ollama_tool_schema_is_mistral_function_format():
    schema = tool_schemas(("get_traffic_forecast",))[0]
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "get_traffic_forecast"


def test_runtime_has_no_coordinator_component():
    runtime = MultiAgentRuntime(use_llm=False)
    assert not hasattr(runtime, "coordinator")
    assert runtime.router is runtime.specialist
