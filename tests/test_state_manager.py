from app.schemas import ContextInterpretation
from app.state_manager import ConversationStateManager


def test_standalone_query_does_not_inherit_previous_state():
    memory = {
        "last_time": "16:20",
        "last_policy": "PCA",
        "last_objective": "balanced",
        "last_constraints_raw": {"ran_subcarriers": 2},
    }
    context = ContextInterpretation(relation="standalone", inherit=[])
    assert ConversationStateManager.scoped_memory(context, memory) == {}


def test_followup_inherits_only_requested_fields():
    memory = {
        "last_time": "19:00",
        "last_tool": "analyze_constrained_allocation",
        "last_policy": "MBA",
        "last_objective": "balanced",
        "last_constraints_raw": {"ran_subcarriers": 2},
    }
    context = ContextInterpretation(
        relation="followup",
        inherit=["time", "constraints"],
    )
    scoped = ConversationStateManager.scoped_memory(context, memory)
    assert scoped == {
        "last_time": "19:00",
        "last_constraints_raw": {"ran_subcarriers": 2},
    }


def test_relative_time_is_applied_deterministically():
    memory = {"last_time": "09:00", "last_tool": "get_traffic_forecast"}
    context = ContextInterpretation(
        relation="followup",
        inherit=["intent", "time"],
        relative_time_offset_minutes=60,
    )
    scoped = ConversationStateManager.scoped_memory(context, memory)
    assert scoped["last_tool"] == "get_traffic_forecast"
    assert scoped["last_time"] == "10:00"
    assert scoped["relative_time_applied"] is True


def test_relative_time_wraps_across_midnight():
    assert ConversationStateManager.apply_relative_minutes("23:30", 60) == "00:30"
    assert ConversationStateManager.apply_relative_minutes("00:15", -30) == "23:45"


def test_explicit_current_constraint_can_override_inherited_constraint():
    previous = {"ran_subcarriers": 2, "pon_subcarriers": 1}
    current = {"pon_subcarriers": 2}
    merged = {**previous, **current}
    assert merged == {"ran_subcarriers": 2, "pon_subcarriers": 2}
