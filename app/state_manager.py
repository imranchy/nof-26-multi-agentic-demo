from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class ConversationStateManager:
    """Authoritative operational state helpers.

    This class never interprets operator language and never chooses a capability.
    It only exposes compact state, performs clock arithmetic, and retrieves stored
    deterministic constraints for argument resolution.
    """

    @staticmethod
    def compact_state(memory: dict[str, Any]) -> dict[str, Any]:
        keep = (
            "last_time",
            "last_tool",
            "last_policy",
            "recommended_policy",
            "last_reference_policy",
            "last_objective",
            "last_constraints_raw",
            "comparison_time_a",
            "comparison_time_b",
        )
        out: dict[str, Any] = {}
        for key in keep:
            value = memory.get(key)
            if value is not None:
                out[key] = dict(value) if isinstance(value, dict) else value
        return out

    @staticmethod
    def apply_relative_minutes(base_time: str, offset_minutes: int) -> str:
        parsed = datetime.strptime(base_time, "%H:%M")
        shifted = parsed + timedelta(minutes=int(offset_minutes))
        return shifted.strftime("%H:%M")

    @staticmethod
    def memory_for_constraints(memory: dict[str, Any]) -> dict[str, int]:
        raw = memory.get("last_constraints_raw", {})
        if not isinstance(raw, dict):
            return {}
        return {str(k): int(v) for k, v in raw.items()}
