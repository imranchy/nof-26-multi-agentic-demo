from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.schemas import ContextInterpretation


class ConversationStateManager:
    """Apply validated, language-independent conversational state transitions."""

    INHERITABLE_FIELDS = {
        "intent",
        "time",
        "policy",
        "objective",
        "constraints",
    }

    @classmethod
    def missing_inherited_fields(
        cls,
        context: ContextInterpretation,
        memory: dict[str, Any],
    ) -> list[str]:
        """Return referenced state fields that do not exist.

        This validates the structured context contract only. It never inspects the
        operator's wording.
        """
        if context.relation != "followup":
            return []

        missing: list[str] = []
        inherit = set(context.inherit) & cls.INHERITABLE_FIELDS

        if "intent" in inherit and not (memory.get("last_tool") and memory.get("last_agent")):
            missing.append("intent")
        if "time" in inherit and not memory.get("last_time"):
            missing.append("time")
        if "policy" in inherit and not any(
            memory.get(key) is not None
            for key in ("last_policy", "recommended_policy", "last_reference_policy")
        ):
            missing.append("policy")
        if "objective" in inherit and memory.get("last_objective") is None:
            missing.append("objective")
        if "constraints" in inherit and not memory.get("last_constraints_raw"):
            missing.append("constraints")

        return missing

    @classmethod
    def scoped_memory(
        cls,
        context: ContextInterpretation,
        memory: dict[str, Any],
    ) -> dict[str, Any]:
        if not memory or context.relation != "followup":
            return {}

        inherit = set(context.inherit) & cls.INHERITABLE_FIELDS
        scoped: dict[str, Any] = {}

        if "intent" in inherit:
            if memory.get("last_tool"):
                scoped["last_tool"] = memory["last_tool"]
            if memory.get("last_agent"):
                scoped["last_agent"] = memory["last_agent"]

        if "time" in inherit:
            if memory.get("last_time"):
                scoped["last_time"] = memory["last_time"]
            if memory.get("comparison_time_a"):
                scoped["comparison_time_a"] = memory["comparison_time_a"]
            if memory.get("comparison_time_b"):
                scoped["comparison_time_b"] = memory["comparison_time_b"]

        if "policy" in inherit:
            for key in ("last_policy", "recommended_policy", "last_reference_policy"):
                if memory.get(key) is not None:
                    scoped[key] = memory[key]

        if "objective" in inherit and memory.get("last_objective") is not None:
            scoped["last_objective"] = memory["last_objective"]

        if "constraints" in inherit and memory.get("last_constraints_raw"):
            scoped["last_constraints_raw"] = dict(memory["last_constraints_raw"])

        if context.relative_time_offset_minutes is not None:
            base = scoped.get("last_time")
            if base is not None:
                scoped["last_time"] = cls.apply_relative_minutes(
                    str(base),
                    context.relative_time_offset_minutes,
                )
                scoped["relative_time_applied"] = True

        return scoped

    @staticmethod
    def apply_relative_minutes(base_time: str, offset_minutes: int) -> str:
        parsed = datetime.strptime(base_time, "%H:%M")
        shifted = parsed + timedelta(minutes=int(offset_minutes))
        return shifted.strftime("%H:%M")

    @staticmethod
    def memory_for_constraints(context_memory: dict[str, Any]) -> dict[str, int]:
        raw = context_memory.get("last_constraints_raw", {})
        if not isinstance(raw, dict):
            return {}
        return {str(k): int(v) for k, v in raw.items()}
