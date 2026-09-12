from app.state_manager import ConversationStateManager


def test_standalone_query_does_not_inherit_previous_state():
    memory = {
        "last_time": "16:20",
        "last_policy": "PCA",
        "last_objective": "balanced",
        "last_constraints_raw": {
            "ran_subcarriers": 2,
        },
    }

    scoped = ConversationStateManager.scoped_memory(
        "Which allocation policy would you use at 21:15?",
        memory,
    )

    assert scoped == {}


def test_constraint_followup_inherits_constraints():
    memory = {
        "last_time": "19:00",
        "last_constraints_raw": {
            "ran_subcarriers": 2,
        },
    }

    scoped = ConversationStateManager.scoped_memory(
        "Also reserve one SC for PON.",
        memory,
    )

    constraints = ConversationStateManager.memory_for_constraints(
        "Also reserve one SC for PON.",
        memory,
    )

    assert scoped["last_time"] == "19:00"
    assert constraints == {
        "ran_subcarriers": 2,
    }


def test_non_followup_constraint_query_does_not_inherit_old_constraints():
    memory = {
        "last_time": "19:00",
        "last_constraints_raw": {
            "ran_subcarriers": 2,
        },
    }

    constraints = ConversationStateManager.memory_for_constraints(
        "Reserve one SC for PON at 21:15.",
        memory,
    )

    assert constraints == {}


def test_explicit_standalone_task_does_not_inherit_policy_or_objective():
    memory = {
        "last_time": "19:00",
        "last_policy": "PCA",
        "recommended_policy": "MBA",
        "last_objective": "min_blocking",
    }

    scoped = ConversationStateManager.scoped_memory(
        "Show me the complete network state at 16:20.",
        memory,
    )

    assert scoped == {}

def test_constraint_followup_keeps_remembered_explicit_constraint_authoritative():
    memory = {
        "last_time": "19:00",
        "last_constraints_raw": {
            "ran_subcarriers": 2,
        },
    }

    previous = ConversationStateManager.memory_for_constraints(
        "Also reserve one SC for PON.",
        memory,
    )

    explicit_current = {"pon_subcarriers": 1}
    merged = {**previous, **explicit_current}

    assert merged == {
        "ran_subcarriers": 2,
        "pon_subcarriers": 1,
    }
