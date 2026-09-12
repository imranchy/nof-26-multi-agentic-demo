from __future__ import annotations

import numpy as np

from app.agents.forecast import ForecastAgent
from app.agents.guardrail import GuardrailAgent
from app.agents.sla import SLAAgent
from app.runtime import MultiAgentRuntime
from app.utils.time_utils import normalize_time


def test_correct_clock_time():
    assert normalize_time("9:30 PM") == "21:30"
    assert normalize_time("21:30") == "21:30"
    assert normalize_time("5:55 AM") == "05:55"


def test_specialist_pipeline_is_consistent():
    """
    Validate the current forecast -> SLA pipeline with the current
    GuardrailAgent API.
    """
    frame = SLAAgent().assess(ForecastAgent().forecast())

    assert np.allclose(
        frame[["enterprise_gbps", "ran_gbps", "pon_gbps"]].sum(axis=1),
        frame["total_gbps"],
        atol=1e-6,
    )

    warnings = GuardrailAgent().validate_frame(frame)
    assert isinstance(warnings, list)


def test_runtime_initializes_current_components_without_llm_call():
    """
    Runtime construction should prepare deterministic tools and memory
    without requiring a coordinator LLM call.
    """
    runtime = MultiAgentRuntime(use_llm=False)

    assert runtime.tools is not None
    assert runtime.guardrail is not None
    assert isinstance(runtime.memory, dict)
    assert len(runtime.frame) == 288


def test_current_deterministic_tool_execution():
    """
    Test the current public deterministic tool dispatcher rather than the
    removed MultiAgentRuntime._execute_tool() legacy helper.
    """
    runtime = MultiAgentRuntime(use_llm=False)

    evidence, fallback = runtime.tools.execute(
        "get_traffic_forecast",
        {"time": "21:15"},
        runtime.memory,
    )

    assert evidence["category"] == "traffic_forecast"
    assert evidence["timestamp"] == "21:15"
    assert evidence["traffic"]["time"] == "21:15"

    traffic = evidence["traffic"]
    assert np.isclose(
        traffic["enterprise_gbps"]
        + traffic["ran_gbps"]
        + traffic["pon_gbps"],
        traffic["total_gbps"],
        atol=0.02,  # values are independently rounded to two decimals for display
    )

    assert isinstance(fallback, str)
    assert fallback


def test_explanation_guardrail_uses_current_api():
    """
    Numeric grounding now belongs to GuardrailAgent.validate_answer(),
    not ExplanationAgent._numbers_are_grounded().
    """
    guardrail = GuardrailAgent()

    evidence = {
        "category": "test_evidence",
        "intervals": 288,
        "normal_percent": 74.7,
    }

    passed, issues = guardrail.validate_answer(
        "There are 288 intervals and the reported value is 74.7%.",
        evidence,
    )

    assert passed
    assert issues == []

    passed, issues = guardrail.validate_answer(
        "There are 999 intervals and the reported value is 74.7%.",
        evidence,
    )

    assert not passed
    assert "unsupported_numeric_claim" in issues


def test_constrained_subcarrier_allocation_uses_current_tool():
    """
    Constrained allocation is now exposed as analyze_constrained_allocation
    through OperatorTools.execute().
    """
    runtime = MultiAgentRuntime(use_llm=False)

    evidence, fallback = runtime.tools.execute(
        "analyze_constrained_allocation",
        {
            "time": "21:15",
            "ran_subcarriers": 2,
            "objective": "balanced",
        },
        runtime.memory,
    )

    assert evidence["category"] == "operator_constraint"
    assert evidence["timestamp"] == "21:15"
    assert evidence["operator_constraints"]["ran"] == 2
    assert evidence["constraint_feasible"] is True

    result = evidence["result"]
    assert result["allocation_counts"]["ran"] == 2
    assert len(result["assignment"]) == 4

    assert isinstance(fallback, str)
    assert fallback


def test_followup_constraint_merge_uses_structured_context_not_language_phrases():
    from app.schemas import ContextInterpretation

    runtime = MultiAgentRuntime(use_llm=False)
    runtime.memory.update({
        "last_time": "19:00",
        "last_constraints_raw": {"ran_subcarriers": 2},
    })
    context = ContextInterpretation(
        relation="followup",
        inherit=["time", "constraints"],
    )
    context_memory = runtime.state_manager.scoped_memory(context, runtime.memory)

    args = runtime._normalize_tool_arguments(
        "analyze_constrained_allocation",
        {"pon_subcarriers": 1},
        context_memory,
    )

    assert args["ran_subcarriers"] == 2
    assert args["pon_subcarriers"] == 1
    assert "enterprise_subcarriers" not in args
    assert args["time"] == "19:00"


def test_relative_followup_time_overrides_model_time_with_python_arithmetic():
    from app.schemas import ContextInterpretation

    runtime = MultiAgentRuntime(use_llm=False)
    runtime.memory.update({"last_time": "09:00", "last_tool": "get_traffic_forecast"})
    context = ContextInterpretation(
        relation="followup",
        inherit=["intent", "time"],
        relative_time_offset_minutes=60,
    )
    context_memory = runtime.state_manager.scoped_memory(context, runtime.memory)
    args = runtime._normalize_tool_arguments(
        "get_traffic_forecast",
        {"time": "09:00"},
        context_memory,
    )
    assert args["time"] == "10:00"
