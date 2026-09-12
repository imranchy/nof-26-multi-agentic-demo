from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd

from app.utils.time_utils import normalize_time


class GuardrailAgent:
    NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?")
    TIME_24_RE = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", re.I)
    TIME_12_RE = re.compile(r"\b(?:1[0-2]|0?[1-9]):[0-5]\d\s*(?:am|pm)\b", re.I)

    # Operator-facing advice that must not be invented merely because
    # a state, risk, blocking value, or ranked interval appears notable.
    UNSUPPORTED_ADVISORY_PATTERNS = (
        "monitor closely",
        "monitor these",
        "requires attention",
        "require attention",
        "may require attention",
        "needs attention",
        "take corrective action",
        "corrective action",
        "investigate immediately",
        "consider reconfiguration",
        "consider reconfiguring",
        "adjust the policy",
        "change the policy",
        "switch the policy",
        "switch policies",
        "no action is required",
        "no action required",
        "no policy change is required",
        "no policy change required",
        "no policy change is recommended",
        "no policy change recommended",
        "no reconfiguration is recommended",
        "no reconfiguration was recommended",
        "no reconfigurations were recommended",
        "maintain network stability",
        "ensure optimal performance",
        "no reconfiguration is required",
        "no reconfiguration required",
        "no reconfigurations are required",
        "no reconfigurations required",
        "no policy changes are required",
        "no policy changes required",
    )

    # Fields whose raw values are ratios/probabilities in [0, 1].
    # For these fields it is safe for the guardrail to recognize an
    # operator-facing percentage representation as equivalent.
    RATIO_FIELD_HINTS = {
        "failure_probability",
        "failure_prone_probability",
        "mean_failure_prone_probability",
        "max_failure_prone_probability",
        "overall_blocking_ratio_epoch",
        "blocking_ratio",
        "mean_blocking_ratio",
        "max_blocking_ratio",
        "fresh_service_ratio",
        "per_class_blocking_ratio",
        "backlog_pressure_ratio",
        "backlog_recovery_ratio",
    }

    def validate_frame(self, frame: pd.DataFrame) -> list[str]:
        warnings: list[str] = []

        required = {
            "time",
            "minute_of_day",
            "enterprise_gbps",
            "ran_gbps",
            "pon_gbps",
            "total_gbps",
            "predicted_state",
            "failure_probability",
            "prediction_confidence",
        }

        missing = required - set(frame.columns)

        if missing:
            raise ValueError(
                f"Forecast frame missing required fields: {sorted(missing)}"
            )

        if len(frame) != 288:
            warnings.append(
                f"Expected 288 five-minute intervals; loaded {len(frame)}."
            )

        if (
            frame[
                [
                    "enterprise_gbps",
                    "ran_gbps",
                    "pon_gbps",
                ]
            ]
            < 0
        ).any().any():
            raise ValueError(
                "Negative traffic values detected."
            )

        summed = frame[
            [
                "enterprise_gbps",
                "ran_gbps",
                "pon_gbps",
            ]
        ].sum(axis=1)

        if not np.allclose(
            summed,
            frame["total_gbps"],
            atol=1e-6,
        ):
            raise ValueError(
                "Aggregate traffic is inconsistent with service traffic."
            )

        if not frame["failure_probability"].between(0, 1).all():
            raise ValueError(
                "Failure-prone scores must lie in [0,1]."
            )

        if not frame["prediction_confidence"].between(0, 1).all():
            raise ValueError(
                "Classifier confidence must lie in [0,1]."
            )

        return warnings

    def validate_answer(
        self,
        answer: str,
        evidence: dict[str, Any],
        query: str | None = None,
    ) -> tuple[bool, list[str]]:
        issues: list[str] = []

        if not answer.strip():
            return False, ["empty_answer"]

        if "GBps" in answer:
            issues.append("invalid_unit_GBps")

        lowered = answer.lower()

        if (
            any(
                term in lowered
                for term in (
                    "fiber cut",
                    "fibre cut",
                    "osnr",
                    "q-factor",
                    "q factor",
                    "ber",
                )
            )
            and evidence.get("category")
            != "physical_layer_out_of_scope"
        ):
            issues.append(
                "unsupported_physical_layer_diagnosis"
            )

        if any(
            term in lowered
            for term in (
                "xgboost",
                "random forest",
                "classifier confidence",
                "rf-v1",
                "xgb-v1",
            )
        ):
            issues.append(
                "implementation_detail_exposed"
            )

        if (
            evidence.get("category")
            == "sla_risk_explanation"
            and any(
                term in lowered
                for term in (
                    "caused by",
                    "due to",
                    "because of",
                    "driven by",
                    "results from",
                )
            )
        ):
            if not evidence.get(
                "causal_attribution_available",
                False,
            ):
                issues.append(
                    "unsupported_causal_claim"
                )

        if (
            evidence.get("category")
            == "network_state"
            and "total capacity" in lowered
        ):
            # The operator state contains both offered traffic and
            # fixed topology capacity; calling offered traffic
            # "total capacity" is a semantic error.
            issues.append(
                "traffic_capacity_confusion"
            )

        if not self._numbers_are_grounded(
            answer,
            evidence,
        ):
            issues.append(
                "unsupported_numeric_claim"
            )

        issues.extend(
            self._categorical_grounding_issues(
                answer,
                evidence,
            )
        )

        issues.extend(
            self._advisory_grounding_issues(
                answer,
                evidence,
                query=query,
            )
        )

        issues.extend(
            self._metric_unit_grounding_issues(
                answer,
                evidence,
            )
        )

        return (
            not issues,
            sorted(set(issues)),
        )

    def _categorical_grounding_issues(
        self,
        answer: str,
        evidence: dict[str, Any],
    ) -> list[str]:
        issues: list[str] = []

        lowered = (
            answer.lower()
            .replace("_", "-")
        )

        actual_states = self._trusted_sla_states(
            evidence
        )

        state_mentions = {
            state
            for state in (
                "normal",
                "degraded",
                "failure-prone",
            )
            if re.search(
                rf"\b{re.escape(state)}\b",
                lowered,
            )
        }

        # Only enforce when wording explicitly asserts a prediction
        # or classification. Explanatory corrections may legitimately
        # mention the user's false premise as well.
        if (
            any(
                x in lowered
                for x in (
                    "predicts",
                    "predicted sla state",
                    "classified as",
                    "classification is",
                    "remained normal",
                    "remained degraded",
                    "remained failure-prone",
                )
            )
            and actual_states
        ):
            if not (
                state_mentions
                & actual_states
            ):
                issues.append(
                    "unsupported_sla_state_claim"
                )

        rec = self._find_key(
            evidence,
            "recommended_policy",
        )

        if rec and "recommend" in lowered:
            mentioned = {
                p
                for p in (
                    "PCA",
                    "MBA",
                    "SAA",
                )
                if re.search(
                    rf"\b{p.lower()}\b",
                    lowered,
                )
            }

            if (
                mentioned
                and str(rec).upper()
                not in mentioned
            ):
                issues.append(
                    "unsupported_recommendation_claim"
                )

        changed = self._find_key(
            evidence,
            "changed",
        )

        if (
            changed is False
            and any(
                x in lowered
                for x in (
                    "recommendation changes",
                    "policy changes",
                    "changes from",
                )
            )
        ):
            issues.append(
                "false_change_claim"
            )

        return issues

    def _advisory_grounding_issues(
        self,
        answer: str,
        evidence: dict[str, Any],
        query: str | None = None,
    ) -> list[str]:
        """Reject operational advice that is absent from deterministic evidence."""
        lowered = answer.lower()

        # Evidence must contain an explicit advisory/recommendation
        # signal before unsolicited operational advice is allowed.
        advisory_evidence = any(
            self._find_key(
                evidence,
                key,
            )
            is not None
            for key in (
                "recommended_policy",
                "recommendation",
                "advisory_action",
                "recommended_action",
                "operator_action",
            )
        )

        if advisory_evidence:
            return []

        for phrase in self.UNSUPPORTED_ADVISORY_PATTERNS:
            if phrase in lowered:
                return [
                    "unsupported_advisory_claim"
                ]

        return []

    def _metric_unit_grounding_issues(
        self,
        answer: str,
        evidence: dict[str, Any],
    ) -> list[str]:
        """Catch semantically invalid metric/unit combinations."""
        lowered = answer.lower()

        category = evidence.get("category")
        metric = evidence.get("metric")

        # Failure-prone risk / probability is dimensionless.
        if (
            "failure-prone risk" in lowered
            or "failure prone risk" in lowered
            or "failure probability" in lowered
        ):
            risk_with_gbps = re.search(
                r"(?:failure[- ]prone risk|failure probability)"
                r"[^.\n]{0,50}\b[-+]?\d+(?:\.\d+)?\s*gbps\b",
                lowered,
            )

            if risk_with_gbps:
                return [
                    "risk_unit_confusion"
                ]

        # Ranked risk discovery should never describe the ranking
        # value as traffic simply because each source row originated
        # from the network forecast.
        if (
            category == "risk_intervals"
            and metric == "failure_probability"
            and "gbps" in lowered
            and (
                "risk" in lowered
                or "probability" in lowered
            )
        ):
            return [
                "risk_unit_confusion"
            ]

        return []

    @classmethod
    def _extract_normalized_times(cls, text: str) -> list[str]:
        """Extract explicit clock expressions and normalize them to HH:MM."""
        values: list[str] = []

        for match in cls.TIME_12_RE.finditer(text):
            normalized = normalize_time(match.group(0))
            if normalized is not None:
                values.append(normalized)

        masked = cls.TIME_12_RE.sub("", text)
        for match in cls.TIME_24_RE.finditer(masked):
            normalized = normalize_time(match.group(0))
            if normalized is not None:
                values.append(normalized)

        return values

    @classmethod
    def _mask_clock_times(cls, text: str) -> str:
        """Remove validated clock expressions before generic number grounding."""
        masked = cls.TIME_12_RE.sub("", text)
        return cls.TIME_24_RE.sub("", masked)

    @classmethod
    def _evidence_clock_times(cls, value: Any) -> set[str]:
        """Collect normalized explicit clock times from deterministic evidence."""
        out: set[str] = set()

        if isinstance(value, dict):
            for child in value.values():
                out.update(cls._evidence_clock_times(child))
            return out

        if isinstance(value, (list, tuple)):
            for child in value:
                out.update(cls._evidence_clock_times(child))
            return out

        if isinstance(value, str):
            out.update(cls._extract_normalized_times(value))

        return out

    @staticmethod
    def _numeric_equivalent(
        value: float,
        candidate: float,
    ) -> bool:
        """
        Return True when two numeric values are equivalent for grounding.

        Allows exact matches plus very small floating-point differences.
        """
        return abs(value - candidate) <= 1e-6

    def _numbers_are_grounded(
        self,
        answer: str,
        evidence: dict[str, Any],
    ) -> bool:
        """Validate numerical claims without confusing clock formats with metrics."""
        answer_times = self._extract_normalized_times(answer)
        evidence_times = self._evidence_clock_times(evidence)

        for answer_time in answer_times:
            if evidence_times and answer_time not in evidence_times:
                return False

        # A clock expression such as 9:30 PM is one semantic timestamp, not
        # two independent numeric claims (9 and 30).
        numeric_answer = self._mask_clock_times(answer)

        allowed = self._numeric_values(evidence)
        display_allowed = self._operator_display_numeric_values(evidence)
        candidates = allowed + display_allowed

        for token in self.NUMBER_RE.findall(numeric_answer):
            value = float(token)
            if not any(
                self._numeric_equivalent(value, candidate)
                for candidate in candidates
            ):
                return False

        return True

    @classmethod
    def _operator_display_numeric_values(
        cls,
        value: Any,
        parent_key: str | None = None,
    ) -> list[float]:
        """
        Generate only semantically valid deterministic display variants.

        Ratio/probability fields may appear as percentages in natural
        operator-facing language. Other numeric fields are never scaled.
        """
        out: list[float] = []

        if (
            isinstance(value, bool)
            or value is None
        ):
            return out

        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            numeric = float(value)

            if not math.isfinite(numeric):
                return out

            if (
                parent_key
                in cls.RATIO_FIELD_HINTS
                and 0.0 <= numeric <= 1.0
            ):
                percentage = 100.0 * numeric

                out.extend(
                    [
                        percentage,
                        round(
                            percentage,
                            1,
                        ),
                        round(
                            percentage,
                            2,
                        ),
                    ]
                )

            return out

        if isinstance(value, dict):
            # rendered_values are already explicit display values.
            rendered = value.get(
                "rendered_values"
            )

            if isinstance(rendered, dict):
                out.extend(
                    cls._numeric_values(
                        rendered
                    )
                )

            for key, item in value.items():
                out.extend(
                    cls._operator_display_numeric_values(
                        item,
                        parent_key=key,
                    )
                )

        elif isinstance(
            value,
            (list, tuple),
        ):
            for item in value:
                out.extend(
                    cls._operator_display_numeric_values(
                        item,
                        parent_key=parent_key,
                    )
                )

        return out

    @classmethod
    def _numeric_values(
        cls,
        value: Any,
    ) -> list[float]:
        out: list[float] = []

        if (
            isinstance(value, bool)
            or value is None
        ):
            return out

        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            if math.isfinite(
                float(value)
            ):
                out.append(
                    float(value)
                )

            return out

        if isinstance(value, dict):
            for item in value.values():
                out.extend(
                    cls._numeric_values(
                        item
                    )
                )

        elif isinstance(
            value,
            (list, tuple),
        ):
            for item in value:
                out.extend(
                    cls._numeric_values(
                        item
                    )
                )

        elif isinstance(value, str):
            out.extend(
                float(x)
                for x in cls.NUMBER_RE.findall(
                    value
                )
            )

        return out

    @classmethod
    def _trusted_sla_states(
        cls,
        value: Any,
    ) -> set[str]:
        states: set[str] = set()

        if isinstance(value, dict):
            sla = value.get("sla")

            if (
                isinstance(sla, dict)
                and sla.get("state")
            ):
                states.add(
                    str(
                        sla["state"]
                    ).replace(
                        "_",
                        "-",
                    )
                )

            # Risk interval evidence uses sla_state rather
            # than a nested sla dictionary.
            if value.get("sla_state"):
                states.add(
                    str(
                        value["sla_state"]
                    ).replace(
                        "_",
                        "-",
                    )
                )

            # Time-range summaries expose state_counts.
            state_counts = value.get(
                "state_counts"
            )

            if isinstance(
                state_counts,
                dict,
            ):
                for state, count in (
                    state_counts.items()
                ):
                    try:
                        if int(count) > 0:
                            states.add(
                                str(
                                    state
                                ).replace(
                                    "_",
                                    "-",
                                )
                            )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

            for key, item in value.items():
                if key == "claimed_state":
                    continue

                states |= (
                    cls._trusted_sla_states(
                        item
                    )
                )

        elif isinstance(value, list):
            for item in value:
                states |= (
                    cls._trusted_sla_states(
                        item
                    )
                )

        return states

    @classmethod
    def _find_key(
        cls,
        value: Any,
        target: str,
    ) -> Any:
        if isinstance(value, dict):
            if target in value:
                return value[target]

            for item in value.values():
                found = cls._find_key(
                    item,
                    target,
                )

                if found is not None:
                    return found

        elif isinstance(value, list):
            for item in value:
                found = cls._find_key(
                    item,
                    target,
                )

                if found is not None:
                    return found

        return None