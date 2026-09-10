from __future__ import annotations

import re
from typing import Any

from app.utils.time_utils import normalize_time as normalize_clock_time


class SemanticResolver:
    """Deterministic normalization/safety layer around Mistral semantics.

    This layer does not replace the LLM. It only catches explicit operator
    language that would be unsafe to route incorrectly, and normalizes
    arguments after the LLM has proposed a plan.
    """

    TIME_24 = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
    TIME_12 = re.compile(
        r"\b(1[0-2]|0?[1-9]):([0-5]\d)\s*(am|pm)\b",
        re.I,
    )

    # SC constraints in this demonstrator concern four physical SCs.
    # Support both numeric and natural-language count expressions.
    SC_NUMBER_WORDS = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
    }

    SC_COUNT_TOKEN = r"(?:zero|one|two|three|four|\d+)"

    NETWORK_TERMS = {
        "network",
        "traffic",
        "sla",
        "risk",
        "policy",
        "policies",
        "pca",
        "mba",
        "saa",
        "blocking",
        "reconfig",
        "reconfiguration",
        "subcarrier",
        "subcarriers",
        "sc",
        "ran",
        "pon",
        "enterprise",
        "allocation",
        "capacity",
        "interval",
        "timestamp",
        "forecast",
        "demand",
        "state",
        "congestion",
        "congested",
        "healthy",
        "healthier",
        "performance",
        "digital twin",
    }

    @classmethod
    def normalize_objective(
        cls,
        query: str,
        proposed: str | None,
        default: str = "balanced",
    ) -> str:
        q = query.lower()

        if (
            any(x in q for x in ("without favoring", "without favouring", "no preference for"))
            and "blocking" in q
            and any(x in q for x in ("stability", "reconfiguration", "churn"))
        ):
            return "balanced"

        if any(
            x in q
            for x in (
                "lowest blocking",
                "minimum blocking",
                "min blocking",
                "least blocking",
                "absolute lowest blocking",
                "minimize blocking",
                "minimise blocking",
                "minimizing blocking",
                "minimising blocking",
                "minimized blocking",
                "minimised blocking",
                "reduce blocking",
                "lowest blocked",
                "serve the most demand",
                "serve as much demand as possible",
                "maximize served",
                "maximise served",
                "maximize served demand",
                "maximise served demand",
                "maximize served traffic",
                "maximise served traffic",
            )
        ):
            return "min_blocking"

        if any(
            x in q
            for x in (
                "fewest reconfig",
                "minimum reconfig",
                "min reconfig",
                "least reconfig",
                "minimum churn",
                "least churn",
                "avoid reconfiguration",
                "avoid unnecessary reconfiguration",
                "avoid reconfig",
                "avoid unnecessary sc changes",
                "controller churn",
                "control-plane changes",
                "control plane changes",
                "maximize stability",
                "maximise stability",
                "minimize reconfiguration",
                "minimise reconfiguration",
                "keep it stable",
                "most stable",
                "stability first",
                "reduce controller changes",
                "few controller changes",
                "as few controller changes as possible",
                "prioritize stability",
                "prioritise stability",
                "prioritizing stability",
                "prioritising stability",
                "stability objective",
                "prefer stability",
                "favour stability",
                "favor stability",
                "favouring stability",
                "favoring stability",
            )
        ):
            return "min_reconfiguration"

        if any(
            x in q
            for x in (
                "sla priority",
                "priority baseline",
                "strict priority",
                "service priority",
                "service-class priority",
                "service class priority",
                "preserve service-class priority",
                "preserve service class priority",
                "prioritize sla",
                "prioritise sla",
                "prioritize service order",
                "prioritise service order",
            )
        ):
            return "sla_priority"

        if any(
            x in q
            for x in (
                "preferable",
                "recommend",
                "best",
                "trade-off",
                "tradeoff",
                "balanced",
                "compromise",
            )
        ):
            return "balanced"

        if proposed in {
            "balanced",
            "min_blocking",
            "min_reconfiguration",
            "sla_priority",
        }:
            return proposed

        return default

    @classmethod
    def explicit_times(cls, query: str) -> list[str]:
        """Extract explicit clock expressions and normalize them to HH:MM."""
        values: list[str] = []

        for match in cls.TIME_12.finditer(query):
            normalized = normalize_clock_time(match.group(0))
            if normalized is not None:
                values.append(normalized)

        # Remove 12-hour expressions before scanning for 24-hour times so
        # the same clock value is not extracted twice.
        masked = cls.TIME_12.sub("", query)

        for match in cls.TIME_24.finditer(masked):
            normalized = normalize_clock_time(match.group(0))
            if normalized is not None:
                values.append(normalized)

        return values

    @classmethod
    def normalize_time(
        cls,
        query: str,
        proposed: str | None,
        memory: dict[str, Any],
        step_minutes: int = 5,
    ) -> str | None:
        explicit = cls.explicit_times(query)

        if explicit:
            return explicit[-1]

        q = query.lower()
        last = memory.get("last_time")

        if last:
            if any(
                x in q
                for x in (
                    "that time",
                    "same time",
                    "at that point",
                    "then",
                )
            ):
                return str(last)

            minute = cls.to_minute(str(last))

            if any(
                x in q
                for x in (
                    "previous interval",
                    "one interval before",
                    "interval before",
                )
            ):
                return cls.from_minute(
                    minute - step_minutes
                )

            if any(
                x in q
                for x in (
                    "next interval",
                    "one interval later",
                    "interval after",
                )
            ):
                return cls.from_minute(
                    minute + step_minutes
                )

            if any(
                x in q
                for x in (
                    "an hour later",
                    "one hour later",
                    "60 minutes later",
                )
            ):
                return cls.from_minute(
                    minute + 60
                )

            if any(
                x in q
                for x in (
                    "an hour earlier",
                    "one hour earlier",
                    "an hour before",
                    "60 minutes earlier",
                )
            ):
                return cls.from_minute(
                    minute - 60
                )

        return proposed

    # ------------------------------------------------------------------
    # SC constraint normalization
    # ------------------------------------------------------------------

    @classmethod
    def _parse_sc_count(
        cls,
        value: str,
    ) -> int | None:
        """Convert a digit or small English number word into an SC count."""
        token = value.strip().lower()

        if token in cls.SC_NUMBER_WORDS:
            return cls.SC_NUMBER_WORDS[token]

        if token.isdigit():
            return int(token)

        return None

    @classmethod
    def _set_constraint(
        cls,
        out: dict[str, int],
        key: str,
        raw_value: str,
    ) -> None:
        """Safely add a parsed SC constraint."""
        value = cls._parse_sc_count(raw_value)

        if value is None:
            return

        out[key] = value

    @classmethod
    def extract_constraints(
        cls,
        query: str,
    ) -> dict[str, int]:
        """Extract explicit per-service SC constraints from operator language.

        Supported examples include:

        - "Keep RAN on 2 subcarriers"
        - "Keep RAN on two subcarriers"
        - "Reserve one SC for PON"
        - "Give Enterprise 1 subcarrier"
        - "2 SCs to RAN"
        - "2 subcarriers to RAN and 1 to Enterprise"
        - "Reserve 1 subcarrier for each service"
        - "Reserve one SC for each service"

        Only explicit allocation constraints are extracted. Objective language
        such as "minimize blocking" is handled separately.
        """
        q = query.lower()
        out: dict[str, int] = {}

        count = cls.SC_COUNT_TOKEN

        service_keys = {
            "enterprise": "enterprise_subcarriers",
            "ran": "ran_subcarriers",
            "pon": "pon_subcarriers",
        }

        service_patterns = {
            "enterprise": r"(?:enterprise|ent\.?)",
            "ran": r"ran",
            "pon": r"pon",
        }

        # --------------------------------------------------------------
        # Special form: one/count SC for EACH service.
        #
        # "Reserve 1 subcarrier for each service."
        # -> Enterprise=1, RAN=1, PON=1
        # --------------------------------------------------------------

        each_service_patterns = (
            re.compile(
                rf"\b({count})\s*"
                rf"(?:sc|scs|subcarrier|subcarriers)\s*"
                rf"(?:for|to)\s+each\s+service\b",
                re.I,
            ),
            re.compile(
                rf"\beach\s+service\s+"
                rf"(?:gets?|receives?|uses?|has|on)\s+"
                rf"({count})\s*"
                rf"(?:sc|scs|subcarrier|subcarriers)\b",
                re.I,
            ),
        )

        for pattern in each_service_patterns:
            match = pattern.search(query)

            if match:
                value = cls._parse_sc_count(
                    match.group(1)
                )

                if value is not None:
                    out[
                        "enterprise_subcarriers"
                    ] = value
                    out[
                        "ran_subcarriers"
                    ] = value
                    out[
                        "pon_subcarriers"
                    ] = value

                break

        # --------------------------------------------------------------
        # Service appears before count.
        #
        # "RAN on 2 subcarriers"
        # "Give Enterprise one SC"
        # "Keep PON at two SCs"
        # "reserve RAN 2 subcarriers"
        # --------------------------------------------------------------

        for service, key in service_keys.items():
            service_re = service_patterns[
                service
            ]

            patterns = (
                re.compile(
                    rf"\b{service_re}\b"
                    rf".{{0,35}}?"
                    rf"\b({count})\s*"
                    rf"(?:sc|scs|subcarrier|subcarriers)\b",
                    re.I,
                ),
                re.compile(
                    rf"\b{service_re}\b"
                    rf"\s+(?:on|at|with|using|gets?|receives?)\s+"
                    rf"({count})\b",
                    re.I,
                ),
            )

            for pattern in patterns:
                match = pattern.search(query)

                if match:
                    cls._set_constraint(
                        out,
                        key,
                        match.group(1),
                    )
                    break

        # --------------------------------------------------------------
        # Count appears before service and explicitly names SC.
        #
        # "2 SCs for RAN"
        # "one subcarrier to PON"
        # --------------------------------------------------------------

        for service, key in service_keys.items():
            service_re = service_patterns[
                service
            ]

            pattern = re.compile(
                rf"\b({count})\s*"
                rf"(?:sc|scs|subcarrier|subcarriers)\s*"
                rf"(?:to|for)\s+"
                rf"{service_re}\b",
                re.I,
            )

            match = pattern.search(query)

            if match:
                cls._set_constraint(
                    out,
                    key,
                    match.group(1),
                )

        # --------------------------------------------------------------
        # Shared-unit shorthand.
        #
        # "Allocate exactly 2 subcarriers to RAN and 1 to Enterprise"
        #
        # The second clause often omits "subcarrier". Only enable this
        # shorthand when the overall query clearly contains SC language.
        # --------------------------------------------------------------

        has_sc_language = bool(
            re.search(
                r"\b(?:sc|scs|subcarrier|subcarriers)\b",
                q,
                re.I,
            )
        )

        if has_sc_language:
            for service, key in service_keys.items():
                service_re = service_patterns[
                    service
                ]

                shorthand = re.compile(
                    rf"\b({count})\s+"
                    rf"(?:to|for)\s+"
                    rf"{service_re}\b",
                    re.I,
                )

                match = shorthand.search(query)

                if match:
                    cls._set_constraint(
                        out,
                        key,
                        match.group(1),
                    )

        return out

    @staticmethod
    def extract_policy(
        query: str,
    ) -> str | None:
        q = query.upper()

        for policy in (
            "PCA",
            "MBA",
            "SAA",
        ):
            if re.search(
                rf"\b{policy}\b",
                q,
            ):
                return policy

        return None

    @classmethod
    def is_policy_counterfactual(
        cls,
        query: str,
    ) -> bool:
        """Return True for explicit single-policy simulation requests."""
        q = query.lower()

        if not cls.extract_policy(query):
            return False

        counterfactual_signals = (
            "what happens if",
            "what if",
            "what would",
            "simulate",
            "counterfactual",
            "performance",
            "perform",
            "outcome",
            "would produce",
            "try ",
            " instead",
            "if we use",
            "if we used",
            "if the controller used",
            "if the controller uses",
        )

        return any(
            signal in q
            for signal in counterfactual_signals
        )

    @staticmethod
    def claimed_sla_state(
        query: str,
    ) -> str | None:
        q = query.lower().replace(
            "-",
            "_",
        )

        if (
            "failure_prone" in q
            or "failure prone" in q
        ):
            return "failure_prone"

        if re.search(
            r"\bdegraded\b",
            q,
        ):
            return "degraded"

        if re.search(
            r"\bnormal\b",
            q,
        ):
            return "normal"

        return None

    @classmethod
    def high_confidence_tool(
        cls,
        query: str,
        memory: dict[str, Any],
    ) -> str | None:
        q = query.lower().strip()
        times = cls.explicit_times(query)

        # ----------------------------------------------------------
        # Explicit SC constraints have highest semantic precedence.
        #
        # If the operator fixes any SC count, this is constrained
        # allocation even when the same sentence also asks for
        # minimum blocking, stability, or another objective.
        # ----------------------------------------------------------

        if cls.extract_constraints(query):
            return "analyze_constrained_allocation"

        # ----------------------------------------------------------
        # Physical-layer boundary
        # ----------------------------------------------------------

        if any(
            x in q
            for x in (
                "osnr",
                "ber",
                "q-factor",
                "q factor",
                "fiber cut",
                "fibre cut",
                "gnpy",
                "physical layer",
                "physical-layer",
                "rx power",
                "launch power",
            )
        ):
            return "decline_physical_layer"

        # ----------------------------------------------------------
        # SLA explanation
        # ----------------------------------------------------------

        if (
            (
                "why" in q
                or "explain" in q
            )
            and any(
                x in q
                for x in (
                    "sla",
                    "failure-prone",
                    "failure prone",
                    "degraded",
                    "classified",
                    "risk",
                )
            )
        ):
            return "explain_sla_risk"

        # ----------------------------------------------------------
        # Two-time comparison
        #
        # Explicit comparison semantics take precedence over range
        # summarization.
        # ----------------------------------------------------------

        if (
            len(times) >= 2
            and any(
                x in q
                for x in (
                    "compare",
                    "healthier",
                    "worse",
                    "better",
                    "difference",
                    "changed between",
                    "change between",
                    "change from",
                    "changed from",
                    "versus",
                    " vs ",
                )
            )
        ):
            return "compare_network_states"

        # ----------------------------------------------------------
        # Continuous range summary
        #
        # Two timestamps plus summary/range semantics represents one
        # range analysis. Objective language is an argument to the
        # range tool, not a competing primary intent.
        # ----------------------------------------------------------

        if (
            len(times) >= 2
            and any(
                x in q
                for x in (
                    "summarize",
                    "summarise",
                    "summary",
                    "summarizing",
                    "summarising",
                    "range",
                    "period",
                )
            )
        ):
            return "summarize_time_range"

        # Natural range forms that do not explicitly say "summary".
        if (
            len(times) >= 2
            and any(
                x in q
                for x in (
                    "from",
                    "between",
                    "over",
                    "during",
                )
            )
            and any(
                x in q
                for x in (
                    "network",
                    "load",
                    "traffic",
                    "risk",
                    "policy behavior",
                    "policy behaviour",
                    "behavior",
                    "behaviour",
                    "period",
                    "range",
                )
            )
        ):
            return "summarize_time_range"

        # ----------------------------------------------------------
        # Ranked/extreme interval discovery
        # ----------------------------------------------------------

        if any(
            x in q
            for x in (
                "highest-risk",
                "highest risk",
                "riskiest",
                "most risky",
                "most at risk",
                "worst interval",
                "worst periods",
                "busiest interval",
                "busiest intervals",
                "peak load",
                "peak-load",
                "highest load",
                "highest traffic",
                "peak traffic",
                "highest blocking",
                "most blocking",
                "blocking peak",
                "highest reconfiguration",
                "most reconfiguration",
                "highest sc reconfiguration",
                "most sc reconfiguration",
                "highest controller churn",
                "most controller churn",
            )
        ):
            return "find_risk_intervals"

        if (
            any(
                x in q
                for x in (
                    "where",
                    "when",
                )
            )
            and any(
                x in q
                for x in (
                    "most sc reconfiguration",
                    "highest sc reconfiguration",
                    "most reconfiguration",
                    "highest reconfiguration",
                    "most controller churn",
                    "highest controller churn",
                )
            )
        ):
            return "find_risk_intervals"

        # ----------------------------------------------------------
        # Single-policy counterfactual
        # ----------------------------------------------------------

        if cls.is_policy_counterfactual(
            query
        ):
            return "simulate_policy_at_time"

        # ----------------------------------------------------------
        # Policy comparison / recommendation
        #
        # This remains below explicit SC constraints and range
        # semantics so secondary objective language cannot hijack
        # those primary intents.
        # ----------------------------------------------------------

        if any(
            x in q
            for x in (
                "minimum blocking",
                "minimize blocking",
                "minimise blocking",
                "lowest blocking",
                "minimum churn",
                "fewest reconfig",
                "minimum reconfig",
                "avoid unnecessary reconfiguration",
                "avoid unnecessary sc changes",
                "controller churn",
                "most stable",
                "maximize stability",
                "maximise stability",
                "strict service priority",
                "service-class priority",
                "service class priority",
                "which policy",
                "compare pca",
                "recommend a policy",
                "preferable policy",
                "best policy",
                "best compromise",
                "makes the most sense overall",
                "makes most sense overall",
            )
        ) or (
            sum(1 for policy in ("pca", "mba", "saa") if re.search(rf"\b{policy}\b", q)) >= 2
            and any(x in q for x in ("choose", "compare", "between", "recommend"))
        ):
            return "compare_policies_at_time"

        # ----------------------------------------------------------
        # Forecast and SLA prediction
        # ----------------------------------------------------------

        if (
            any(
                x in q
                for x in (
                    "traffic",
                    "demand",
                    "load",
                    "busy",
                )
            )
            and any(
                x in q
                for x in (
                    "predict",
                    "forecast",
                    "expect",
                    "expected",
                    "what traffic",
                    "outlook",
                )
            )
            and any(
                x in q
                for x in (
                    "traffic",
                    "demand",
                    "load",
                    "busy",
                    "services",
                )
            )
        ):
            return "get_traffic_forecast"

        if (
            any(x in q for x in ("traffic", "load"))
            and any(x in q for x in ("sla", "risk"))
            and any(x in q for x in ("sc", "subcarrier", "allocation", "policy state"))
        ):
            return "get_network_state_at_time"

        if any(
            x in q
            for x in (
                "sla state",
                "sla risk",
                "predicted sla",
                "predicted state",
                "network risk",
                "failure risk",
                "failure-prone risk",
                "failure prone risk",
                "risk state",
                "what is the sla risk",
                "what's the sla risk",
                "failure-prone",
                "failure prone",
                "how risky",
            )
        ):
            return "get_sla_prediction"

        if any(
            x in q
            for x in (
                "network state",
                "operator state",
                "network status",
                "what is happening",
                "what's happening",
                "how does the network look",
                "operator snapshot",
                "network snapshot",
                "what's going on",
                "what is going on",
            )
        ):
            return "get_network_state_at_time"

        # ----------------------------------------------------------
        # Relative follow-ups preserve previous analytical intent.
        # ----------------------------------------------------------

        if (
            any(
                x in q
                for x in (
                    "an hour later",
                    "one hour later",
                    "60 minutes later",
                    "an hour earlier",
                    "one hour earlier",
                    "60 minutes earlier",
                    "previous interval",
                    "next interval",
                    "that time",
                    "same time",
                )
            )
            and memory.get("last_tool")
        ):
            last = str(
                memory["last_tool"]
            )

            if last in {
                "get_network_state_at_time",
                "get_traffic_forecast",
                "get_sla_prediction",
                "explain_sla_risk",
                "compare_policies_at_time",
                "simulate_policy_at_time",
                "analyze_constrained_allocation",
            }:
                return last

        if (
            any(
                x in q
                for x in (
                    "that policy",
                    "the recommended policy",
                )
            )
            and any(
                x in q
                for x in (
                    "simulate",
                    "performance",
                    "what happens",
                    "show",
                )
            )
        ):
            return "simulate_policy_at_time"

        # ----------------------------------------------------------
        # Generic out-of-domain protection
        # ----------------------------------------------------------

        has_network_term = any(
            term in q
            for term in cls.NETWORK_TERMS
        )

        has_time = bool(times)

        followup = any(
            x in q
            for x in (
                "that time",
                "same time",
                "that policy",
                "an hour later",
                "an hour earlier",
                "previous interval",
                "next interval",
                "what about",
            )
        )

        if (
            not has_network_term
            and not has_time
            and not followup
        ):
            return "decline_out_of_scope"

        return None

    @classmethod
    def fallback_plan(
        cls,
        query: str,
        memory: dict[str, Any],
    ) -> list[
        tuple[str, dict[str, Any]]
    ] | None:
        """Safe deterministic fallback after structured LLM output fails."""
        tool = cls.high_confidence_tool(
            query,
            memory,
        )

        if tool:
            return [
                (
                    tool,
                    {},
                )
            ]

        # A standalone time-centric question can safely default to a
        # full network-state view.
        if (
            cls.explicit_times(query)
            and any(
                x in query.lower()
                for x in (
                    "what",
                    "show",
                    "status",
                    "state",
                    "look",
                )
            )
        ):
            return [
                (
                    "get_network_state_at_time",
                    {},
                )
            ]

        return None

    @staticmethod
    def to_minute(
        value: str,
    ) -> int:
        hour, minute = [
            int(v)
            for v in value.split(":")
        ]

        return (
            hour * 60
            + minute
        )

    @staticmethod
    def from_minute(
        value: int,
    ) -> str:
        value %= 1440

        return (
            f"{value // 60:02d}:"
            f"{value % 60:02d}"
        )