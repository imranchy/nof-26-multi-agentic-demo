from app.state_manager import ConversationStateManager


def test_compact_state_exposes_only_authoritative_operational_fields():
    memory = {
        "last_time": "16:20",
        "last_tool": "get_network_state_at_time",
        "last_policy": "PCA",
        "last_objective": "balanced",
        "last_constraints_raw": {"ran_subcarriers": 2},
        "last_result": {"large": "payload"},
        "unrelated": 123,
    }
    assert ConversationStateManager.compact_state(memory) == {
        "last_time": "16:20",
        "last_tool": "get_network_state_at_time",
        "last_policy": "PCA",
        "last_objective": "balanced",
        "last_constraints_raw": {"ran_subcarriers": 2},
    }


def test_relative_time_is_applied_deterministically():
    assert ConversationStateManager.apply_relative_minutes("09:00", 60) == "10:00"


def test_relative_time_wraps_across_midnight():
    assert ConversationStateManager.apply_relative_minutes("23:30", 60) == "00:30"
    assert ConversationStateManager.apply_relative_minutes("00:15", -30) == "23:45"


def test_constraint_memory_is_copied_and_typed():
    memory = {"last_constraints_raw": {"ran_subcarriers": "2", "pon_subcarriers": 1}}
    assert ConversationStateManager.memory_for_constraints(memory) == {
        "ran_subcarriers": 2,
        "pon_subcarriers": 1,
    }


def test_compact_state_does_not_mutate_source_memory():
    memory = {"last_constraints_raw": {"ran_subcarriers": 2}}
    state = ConversationStateManager.compact_state(memory)
    state["last_constraints_raw"]["ran_subcarriers"] = 3
    assert memory["last_constraints_raw"]["ran_subcarriers"] == 2
