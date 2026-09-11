from __future__ import annotations

from typing import Any


class ConversationStateManager:
    """
    Scope conversation memory so genuine follow-ups inherit relevant state
    while standalone requests are protected from unrelated prior context.
    """

    FOLLOWUP_MARKERS = (
        "also",
        "instead",
        "same time",
        "that time",
        "at that time",
        "that point",
        "then",
        "what about",
        "how about",
        "and now",
        "in addition",
        "as well",
        "next interval",
        "previous interval",
        "one interval later",
        "one interval before",
        "an hour later",
        "an hour earlier",
        "use that",
        "keep that",
        "validate that",
        "check that",
    )

    CONSTRAINT_FOLLOWUP_MARKERS = (
        "also",
        "in addition",
        "as well",
        "and keep",
        "and give",
        "reserve another",
        "keep the rest",
        "with the rest",
    )

    @classmethod
    def is_followup(cls, query: str) -> bool:
        q = query.lower().strip()

        return any(
            marker in q
            for marker in cls.FOLLOWUP_MARKERS
        )

    @classmethod
    def is_constraint_followup(cls, query: str) -> bool:
        q = query.lower().strip()

        return any(
            marker in q
            for marker in cls.CONSTRAINT_FOLLOWUP_MARKERS
        )

    @classmethod
    def scoped_memory(
        cls,
        query: str,
        memory: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Return only memory appropriate for interpreting this turn.

        A standalone query gets almost no inherited semantic state.
        A genuine follow-up gets the relevant previous state.
        """

        if not memory:
            return {}

        if cls.is_followup(query):
            return dict(memory)

        # Standalone request:
        # do not leak previous policy/objective/constraints/task intent.
        #
        # Keep no semantic values here because explicit values in the
        # current query and configured defaults should determine execution.
        return {}

    @classmethod
    def memory_for_constraints(
        cls,
        query: str,
        memory: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Constraint state is inherited only for additive follow-ups.
        """

        if not cls.is_constraint_followup(query):
            return {}

        return dict(
            memory.get(
                "last_constraints_raw",
                {},
            )
        )