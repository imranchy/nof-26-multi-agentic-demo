from __future__ import annotations

import numpy as np

from app.agents.coordinator import CoordinatorAgent
from app.agents.explanation import ExplanationAgent
from app.agents.forecast import ForecastAgent
from app.agents.guardrail import GuardrailAgent
from app.agents.recovery import RecoveryAgent
from app.agents.sla import SLAAgent
from app.runtime import MultiAgentRuntime


def test_correct_clock_time():
    frame = ForecastAgent().forecast()
    assert frame.iloc[0].time == "00:00"
    assert frame.iloc[-1].time == "23:55"


def test_specialist_pipeline_is_consistent():
    frame = RecoveryAgent().recommend(SLAAgent().assess(ForecastAgent().forecast()))
    assert np.allclose(frame[["enterprise_gbps", "ran_gbps", "pon_gbps"]].sum(axis=1), frame.total_gbps)
    assert isinstance(GuardrailAgent().validate(frame), list)
    assert set(frame.candidate_layout.unique()) <= {"EE|P|R", "E|PP|R", "E|P|RR"}
    assert (frame.estimated_overflow_gbps >= 0).all()


def test_native_tool_call_is_executed_and_answered(monkeypatch):
    coordinator = CoordinatorAgent()
    replies = iter([
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "find_service_peak", "arguments": {"service": "ran"}}}],
        },
        {"role": "assistant", "content": "RAN traffic peaks at 20:25 with 46.48 Gbps."},
    ])
    monkeypatch.setattr(coordinator, "_chat", lambda messages, include_tools: next(replies))
    called = []

    def execute(name, arguments):
        called.append((name, arguments))
        return {"service": "RAN", "intervals": [{"time": "20:25", "service_load_gbps": 46.48}]}

    answer, name, arguments, evidence = coordinator.run("When does RAN peak?", execute)
    assert called == [("find_service_peak", {"service": "ran"})]
    assert name == "find_service_peak"
    assert evidence["service"] == "RAN"
    assert "20:25" in answer


def test_runtime_demo_evidence():
    runtime = MultiAgentRuntime()
    cases = [
        ("summarize_day_ahead", {}, lambda e: e["state_counts"] == {"normal": 215, "degraded": 38, "failure_prone": 35}),
        ("find_next_sla_risk", {"state": "any_non_normal"}, lambda e: e["interval"]["time"] == "17:00"),
        ("diagnose_highest_risk", {}, lambda e: e["diagnosis"]["dominant_service"] == "RAN"),
        ("recommend_subcarrier_allocation", {}, lambda e: e["recommendation"]["estimated_overflow_gbps"] == 13.66),
        ("check_allocation_feasibility", {}, lambda e: e["recommendation"]["allocation_feasible"] is False),
        ("find_service_peak", {"service": "ran"}, lambda e: e["intervals"][0] == {"time": "20:25", "service_load_gbps": 46.48}),
    ]
    for name, arguments, assertion in cases:
        assert assertion(runtime._execute_tool(name, arguments, []))


def test_explanation_guardrails():
    evidence = {"intervals": 288, "normal_percent": 74.7}
    assert ExplanationAgent._numbers_are_grounded("There are 288 intervals and 74.7% are normal.", evidence)
    assert not ExplanationAgent._numbers_are_grounded("This equals 212.16 hours.", evidence)
    assert not ExplanationAgent._semantics_are_grounded(
        "There is a 13.2% chance of degraded operation.",
        {"state_distribution_percent": {"degraded": 13.2}},
    )
