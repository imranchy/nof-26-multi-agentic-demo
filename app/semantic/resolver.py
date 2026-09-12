from __future__ import annotations

from typing import Any

from app import config
from app.utils.time_utils import normalize_time as normalize_clock_time


class SemanticResolver:
    """Language-independent validation for Mistral-produced structured semantics.

    Natural-language interpretation belongs to Mistral. This layer only validates
    canonical values before deterministic execution.
    """

    POLICIES = set(config.policy_ids())
    OBJECTIVES = set(config.recommendation_objectives())
    METRICS = {"failure_probability", "total_gbps", "blocking", "reconfiguration"}
    SLA_STATES = {"normal", "degraded", "failure_prone"}
    CONSTRAINT_KEYS = {"enterprise_subcarriers", "ran_subcarriers", "pon_subcarriers"}

    @staticmethod
    def normalize_time_value(value: Any) -> str | None:
        if value is None:
            return None
        normalized = normalize_clock_time(str(value))
        return normalized

    @classmethod
    def normalize_policy(cls, value: Any) -> str | None:
        if value is None:
            return None
        policy = str(value).strip().upper()
        return policy if policy in cls.POLICIES else None

    @classmethod
    def normalize_objective_value(cls, value: Any, default: str = "balanced") -> str:
        objective = str(value).strip() if value is not None else ""
        return objective if objective in cls.OBJECTIVES else default

    @classmethod
    def normalize_metric(cls, value: Any, default: str = "failure_probability") -> str:
        metric = str(value).strip() if value is not None else ""
        return metric if metric in cls.METRICS else default

    @classmethod
    def normalize_claimed_state(cls, value: Any) -> str | None:
        if value is None:
            return None
        state = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        return state if state in cls.SLA_STATES else None

    @classmethod
    def normalize_constraints(cls, arguments: dict[str, Any]) -> dict[str, int]:
        out: dict[str, int] = {}
        for key in cls.CONSTRAINT_KEYS:
            if key not in arguments or arguments[key] is None:
                continue
            try:
                value = int(arguments[key])
            except (TypeError, ValueError):
                continue
            if 0 <= value <= 4:
                out[key] = value
        return out

    @staticmethod
    def normalize_top_k(value: Any, default: int = 3) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return min(10, max(1, parsed))
