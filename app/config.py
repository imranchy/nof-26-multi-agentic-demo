from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models"
CONFIG_DIR = ROOT / "config"
POLICY_DIR = ROOT / "policies"
PROMPT_DIR = ROOT / "prompts"
VALIDATION_DIR = ROOT / "validation"

FORECAST_DATA = DATA_DIR / "source" / "scenarios_00200001_to_00200365_5min.csv"
ALLOCATION_DATA = DATA_DIR / "source" / "SC_Allocation_Output_Data_Dictionary.xlsx"
PRECOMPUTED_FORECAST = DATA_DIR / "prepared" / "xgboost_day_ahead_predictions.csv"
REGRESSION_METRICS = DATA_DIR / "prepared" / "day_ahead_metrics.csv"

FORECAST_MODEL = MODEL_DIR / "xgboost_day_ahead_model.joblib"
CLASSIFIER_MODEL = MODEL_DIR / "sla_random_forest.joblib"
CLASSIFIER_METADATA = MODEL_DIR / "sla_random_forest.metadata.json"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b")

REQUIRE_LLM = (
    os.getenv("NOF_REQUIRE_LLM", "1").strip().lower()
    not in {"0", "false", "no"}
)

SERVICES = (
    "enterprise",
    "ran",
    "pon",
)

CLASSIFIER_FEATURES = (
    "enterprise_gbps",
    "ran_gbps",
    "pon_gbps",
    "total_gbps",
    "hour_sin",
    "hour_cos",
    "minute_of_day_sin",
    "minute_of_day_cos",
)


@lru_cache(maxsize=None)
def load_yaml(name: str) -> dict[str, Any]:
    """
    Load a YAML file from config/.
    """
    path = CONFIG_DIR / name

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        )

    value = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )

    return value or {}


@lru_cache(maxsize=None)
def load_policy_yaml(policy_id: str) -> dict[str, Any]:
    """
    Load policy metadata from policies/<policy>.yaml.
    """
    path = POLICY_DIR / f"{policy_id.lower()}.yaml"

    if not path.exists():
        raise FileNotFoundError(
            f"Policy metadata not found: {path}"
        )

    value = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )

    return value or {}


def _prompt_spec(role: str) -> dict[str, Any]:
    """
    Return the prompt configuration for a specific role.
    """
    cfg = load_yaml("prompts.yaml").get("prompts", {})

    if role not in cfg:
        raise KeyError(
            f"Prompt role not configured: {role}"
        )

    return cfg[role]


@lru_cache(maxsize=None)
def _read_prompt(relative_path: str) -> str:
    """
    Read one Markdown prompt module from prompts/.
    """
    path = PROMPT_DIR / relative_path

    if not path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {path}"
        )

    return path.read_text(
        encoding="utf-8"
    ).strip()


def prompt_version(role: str) -> str:
    """
    Return configured prompt version for provenance/evaluation.
    """
    return str(
        _prompt_spec(role).get(
            "version",
            "unknown",
        )
    )


def coordinator_prompt() -> str:
    """
    Build the complete coordinator prompt.

    The coordinator must see all routing modules because the
    operator's intent is not known until Mistral interprets
    the request.
    """
    spec = _prompt_spec("coordinator")

    parts: list[str] = []

    base_path = spec.get("base")

    if not base_path:
        raise KeyError(
            "Coordinator prompt configuration is missing 'base'."
        )

    parts.append(
        _read_prompt(base_path)
    )

    for module_path in spec.get("modules", []):
        parts.append(
            _read_prompt(module_path)
        )

    style_spec = _prompt_spec("operator_style")
    style_file = style_spec.get("file")

    if not style_file:
        raise KeyError(
            "Operator style prompt configuration is missing 'file'."
        )

    parts.append(
        _read_prompt(style_file)
    )

    return "\n\n".join(parts)


EXPLAINER_CATEGORY_MAP: dict[str, str | None] = {
    # Traffic
    "traffic_forecast": "traffic_prediction",

    # SLA / risk
    "sla_prediction": "sla_risk_state",
    "sla_risk_explanation": "sla_risk_state",

    # Full state
    "network_state": "full_network_state",

    # Policy
    "policy_comparison": "policy_comparison_balanced",
    "policy_counterfactual": "policy_counterfactual",

    # Constraints
    "operator_constraint": "sc_constraints",

    # Temporal analysis
    "cross_time_comparison": "temporal_comparison",

    # Range / risk discovery
    "risk_intervals": "range_risk_discovery",
    "time_range_summary": "range_risk_discovery",

    # Multi-tool / context-heavy responses
    "multi_tool_analysis": "conversational_context",

    # Out-of-scope cases use only the base explainer + style
    "physical_layer_out_of_scope": None,
    "generic_out_of_scope": None,
}


def explainer_prompt(
    evidence_category: str | None = None,
) -> str:
    """
    Build the explainer prompt.

    Unlike the coordinator, the explainer knows which deterministic
    evidence category was produced. Therefore it receives only the
    relevant specialist prompt module.
    """
    spec = _prompt_spec("explainer")

    parts: list[str] = []

    base_path = spec.get("base")

    if not base_path:
        raise KeyError(
            "Explainer prompt configuration is missing 'base'."
        )

    parts.append(
        _read_prompt(base_path)
    )

    module_key = EXPLAINER_CATEGORY_MAP.get(
        evidence_category
    )

    if module_key:
        modules = spec.get("modules", {})
        module_path = modules.get(module_key)

        if module_path:
            parts.append(
                _read_prompt(module_path)
            )

    style_spec = _prompt_spec("operator_style")
    style_file = style_spec.get("file")

    if not style_file:
        raise KeyError(
            "Operator style prompt configuration is missing 'file'."
        )

    parts.append(
        _read_prompt(style_file)
    )

    return "\n\n".join(parts)


def operator_prompt() -> str:
    """
    Backward-compatible alias for older code that still imports
    operator_prompt().
    """
    return coordinator_prompt()


def network_parameters() -> dict[str, Any]:
    """
    Return network parameters from config/network.yaml.
    """
    return load_yaml("network.yaml")["network"]


def controller_parameters() -> dict[str, Any]:
    """
    Return controller parameters from config/network.yaml.
    """
    return load_yaml("network.yaml")["controller"]


def service_weights() -> dict[str, float]:
    """
    Return configured SLA/service weights.
    """
    return {
        key: float(value)
        for key, value in load_yaml("sla.yaml")[
            "service_weights"
        ].items()
    }


def service_priority() -> list[str]:
    """
    Return configured service priority order.
    """
    return [
        str(value)
        for value in load_yaml("sla.yaml")[
            "service_priority"
        ]
    ]