from app import config


def test_router_v3_prompt_is_loaded():
    prompt = config.tool_router_prompt()

    assert "NoF direct Mistral tool router v3" in prompt
    assert "Canonical routing examples v3" in prompt
    assert "Operator requests may be written in English, Italian, Portuguese, German, French, Spanish" in prompt

    for tool_name in (
        "get_traffic_forecast",
        "get_sla_prediction",
        "get_network_state_at_time",
        "compare_policies_at_time",
        "simulate_policy_at_time",
        "analyze_constrained_allocation",
        "compare_network_states",
        "find_risk_intervals",
        "summarize_time_range",
        "decline_out_of_scope",
        "decline_physical_layer",
    ):
        assert tool_name in prompt


def test_router_v3_teaches_contrastive_boundaries():
    prompt = config.tool_router_prompt()

    assert "Policy comparison vs SC constraint" in prompt
    assert "Objective-aware policy vs range summary" in prompt
    assert "Counterfactual vs current network state" in prompt
    assert "Out of scope vs clarification" in prompt
    assert "Do not invent SC counts" in prompt


def test_router_v3_uses_compact_english_examples_not_six_language_duplication():
    prompt = config.tool_router_prompt()

    # The prompt remains language-agnostic but does not carry six translated
    # copies of every example.
    assert "EN:" not in prompt
    assert "IT:" not in prompt
    assert "PT:" not in prompt
    assert "DE:" not in prompt
    assert "FR:" not in prompt
    assert "ES:" not in prompt

    # Canonical examples still vary the important argument values.
    for time_value in ("21:15", "11:25", "16:20", "17:35", "19:25", "13:50", "10:45"):
        assert time_value in prompt

    for policy in ("PCA", "MBA", "SAA"):
        assert policy in prompt
