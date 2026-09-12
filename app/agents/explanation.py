from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

from app import config
from app.agents.guardrail import GuardrailAgent


@dataclass
class ExplanationResult:
    accepted_answer: str
    raw_answer: str | None
    grounding_passed: bool
    issues: list[str]


class ExplanationAgent:
    def __init__(
        self,
        guardrail: GuardrailAgent | None = None,
    ) -> None:
        self.guardrail = guardrail or GuardrailAgent()

    def explain(
        self,
        query: str,
        evidence: dict,
        fallback: str,
    ) -> ExplanationResult:
        evidence_category = evidence.get("category")

        operator_evidence = self._operator_evidence(
            evidence,
            query,
        )

        prompt = f"""{config.explainer_prompt(evidence_category)}

Operator question:
{query}

Validated deterministic evidence:
{json.dumps(operator_evidence, ensure_ascii=False)}

Compose one concise operator-facing answer, normally under 130 words.
"""

        try:
            payload = {
                "model": config.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 220,
                },
            }

            request = Request(
                f"{config.OLLAMA_URL}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                },
            )

            with urlopen(
                request,
                timeout=60,
            ) as response:
                body = json.loads(response.read())

            raw = str(
                body.get("response", "")
            ).strip()

            passed, issues = self.guardrail.validate_answer(
                raw,
                evidence,
                query=query,
            )

            if passed:
                return ExplanationResult(
                    raw,
                    raw,
                    True,
                    [],
                )

            return ExplanationResult(
                fallback,
                raw,
                False,
                issues,
            )

        except Exception as exc:
            # After deterministic tool execution, explanation failure
            # must never discard the grounded result. The UI receives
            # the deterministic fallback.
            tag = (
                "explanation_unavailable"
                if config.REQUIRE_LLM
                else "llm_disabled_or_unavailable"
            )

            return ExplanationResult(
                fallback,
                None,
                False,
                [f"{tag}:{type(exc).__name__}"],
            )

    @classmethod
    def _operator_evidence(
        cls,
        value,
        query: str,
    ):
        """Hide implementation details and shape category-specific evidence."""
        provenance_requested = any(
            term in query.lower()
            for term in (
                "which model",
                "what model",
                "algorithm",
                "implementation",
                "provenance",
                "how is the prediction produced",
            )
        )

        hidden = {
            "prediction_confidence",
            "severity_score",
            "internal_probabilities",
        }

        if not provenance_requested:
            hidden |= {
                "provenance",
                "model",
                "version",
                "execution_mode",
                "saved_model_inference",
                "source_of_truth",
            }

        if isinstance(value, dict):
            category = value.get("category")

            # ------------------------------------------------------
            # Policy counterfactual
            # ------------------------------------------------------

            if category == "policy_counterfactual":
                return cls._shape_policy_counterfactual(
                    value,
                    query,
                    hidden,
                )

            if category == "policy_comparison":
                return cls._shape_policy_comparison(
                    value,
                    query,
                    hidden,
                )

            # ------------------------------------------------------
            # Operator-constrained SC allocation
            # ------------------------------------------------------

            if category == "operator_constraint":
                return cls._shape_operator_constraint(
                    value,
                    query,
                    hidden,
                )

            if category == "cross_time_comparison":
                return cls._shape_cross_time_comparison(
                    value,
                    query,
                    hidden,
                )

            # ------------------------------------------------------
            # Ranked risk/load/blocking/reconfiguration intervals
            # ------------------------------------------------------

            if category == "risk_intervals":
                return cls._shape_risk_intervals(
                    value,
                    query,
                    hidden,
                )

            # ------------------------------------------------------
            # Continuous time-range summary
            # ------------------------------------------------------

            if category == "time_range_summary":
                return cls._shape_time_range_summary(
                    value,
                    query,
                    hidden,
                )

            return {
                k: cls._operator_evidence(v, query)
                for k, v in value.items()
                if k not in hidden
            }

        if isinstance(value, list):
            return [
                cls._operator_evidence(v, query)
                for v in value
            ]

        return value

    @classmethod
    def _shape_policy_comparison(
        cls,
        value: dict,
        query: str,
        hidden: set[str],
    ) -> dict:
        """Expose only operator-facing values needed for a policy comparison.

        Raw policy-engine traffic/capacity values are intentionally hidden here.
        The explainer receives rendered blocking values plus reconfiguration counts,
        which prevents it from deriving or inventing unrelated traffic/SLA numbers.
        """
        shaped: dict = {
            "category": "policy_comparison",
        }

        for key in (
            "timestamp",
            "objective",
            "recommended_policy",
            "recommendation_is_advisory",
            "rendered_values",
        ):
            if key in value and key not in hidden:
                shaped[key] = cls._operator_evidence(value[key], query)

        results = value.get("policy_results")
        if isinstance(results, dict):
            compact: dict = {}
            for policy, result in results.items():
                if not isinstance(result, dict):
                    continue
                compact[policy] = {
                    key: cls._operator_evidence(item, query)
                    for key, item in result.items()
                    if key in {"policy", "assignment_label", "reconfig_count"}
                    and key not in hidden
                }
            shaped["policy_results"] = compact

        return shaped

    @classmethod
    def _shape_policy_counterfactual(
        cls,
        value: dict,
        query: str,
        hidden: set[str],
    ) -> dict:
        """Expose only policy-counterfactual evidence relevant to generation."""
        allowed_top_level = {
            "category",
            "timestamp",
            "policy",
            "simulated_result",
            "counterfactual",
            "advisory",
            "rendered_values",
        }

        shaped = {
            k: cls._operator_evidence(v, query)
            for k, v in value.items()
            if k in allowed_top_level and k not in hidden
        }

        result = shaped.get("simulated_result")

        if isinstance(result, dict):
            allowed_result_fields = {
                "policy",
                "assignment",
                "assignment_label",
                "allocation_counts",
                "active_subcarriers",
                "idle_subcarriers",
                "demand_gbps",
                "capacity_gbps",
                "served_new_gbps",
                "blocked_new_gbps",
                "overall_blocking_ratio_epoch",
                "blocking_event",
                "per_class_blocking_ratio",
                "fresh_service_ratio",
                "reconfig_event",
                "reconfig_count",
                "weighted_reconfig_cost",
            }

            shaped["simulated_result"] = {
                k: cls._operator_evidence(v, query)
                for k, v in result.items()
                if k in allowed_result_fields
                and k not in hidden
            }

        return shaped

    @classmethod
    def _shape_operator_constraint(
        cls,
        value: dict,
        query: str,
        hidden: set[str],
    ) -> dict:
        """Expose only evidence needed to explain a constrained SC allocation."""
        shaped: dict = {
            "category": "operator_constraint",
        }

        # Keep only the high-level deterministic facts needed for a concise
        # operator-facing constrained-allocation explanation.
        for key in (
            "timestamp",
            "operator_constraints",
            "constraint_feasible",
            "reason",
            "objective",
            "reference_policy",
            "rendered_values",
        ):
            if key in value and key not in hidden:
                shaped[key] = cls._operator_evidence(
                    value[key],
                    query,
                )

        # For infeasible constraints there is no valid allocation result
        # to explain. Return the reason without exposing unrelated fields.
        if value.get("constraint_feasible") is False:
            return shaped

        result = value.get("result")

        if not isinstance(result, dict):
            return shaped

        # Closed evidence scope for a normal constrained-allocation answer.
        # Deliberately exclude traffic/capacity/served-demand details because
        # those values are not needed to answer the allocation question and
        # previously encouraged over-generation.
        allowed_result_fields = {
            "policy",
            "assignment",
            "assignment_label",
            "overall_blocking_ratio_epoch",
            "fresh_service_ratio",
            "reconfig_event",
            "reconfig_count",
        }

        shaped["result"] = {
            key: cls._operator_evidence(item, query)
            for key, item in result.items()
            if key in allowed_result_fields
            and key not in hidden
        }

        return shaped

    @classmethod
    def _shape_cross_time_comparison(
        cls,
        value: dict,
        query: str,
        hidden: set[str],
    ) -> dict:
        """Expose only deterministic fields needed for a two-time comparison."""

        shaped: dict = {
            "category": "cross_time_comparison",
        }

        for key in (
            "time_a",
            "time_b",
            "policy",
            "rendered_values",
        ):
            if key in value and key not in hidden:
                shaped[key] = cls._operator_evidence(
                    value[key],
                    query,
                )

        # Endpoint values are deliberately restricted to categorical state labels.
        # Numerical comparison should come from the already-calculated delta fields
        # and rendered_values, not from asking the LLM to subtract endpoints.
        for state_key in ("state_a", "state_b"):
            state = value.get(state_key)
            if not isinstance(state, dict):
                continue
            sla = state.get("sla")
            if isinstance(sla, dict) and "state" in sla:
                shaped[state_key] = {
                    "sla": {"state": cls._operator_evidence(sla["state"], query)}
                }

        delta = value.get("delta_b_minus_a")

        if isinstance(delta, dict):
            # Expose operator-facing precision only. The deterministic tool may
            # retain higher precision internally, but the explainer should not
            # increase the precision shown to operators.
            shaped["delta_b_minus_a"] = {
                "total_gbps": round(float(delta.get("total_gbps", 0.0)), 2),
                "reconfig_count": int(delta.get("reconfig_count", 0)),
            }

        return shaped

    @classmethod
    def _shape_risk_intervals(
        cls,
        value: dict,
        query: str,
        hidden: set[str],
    ) -> dict:
        """Expose only fields relevant to the requested discovery metric."""
        metric = str(
            value.get("metric")
            or "failure_probability"
        )

        shaped: dict = {
            "category": "risk_intervals",
            "metric": metric,
        }

        if "top_k" in value:
            shaped["top_k"] = value["top_k"]

        if "policy" in value:
            shaped["policy"] = value["policy"]

        intervals = value.get("intervals", [])

        if not isinstance(intervals, list):
            return shaped

        shaped_intervals = []

        for item in intervals:
            if not isinstance(item, dict):
                continue

            # Failure-prone risk discovery:
            # expose only ranking time + risk.
            if metric == "failure_probability":
                allowed = {
                    "time",
                    "failure_risk_percent",
                }

            # Peak/busiest traffic discovery:
            # expose only ranking time + total traffic.
            elif metric == "total_gbps":
                allowed = {
                    "time",
                    "total_gbps",
                }

            # Blocking discovery:
            # expose only ranking time + policy + blocking.
            elif metric == "blocking":
                allowed = {
                    "time",
                    "policy",
                    "blocking_ratio",
                }

            # Reconfiguration discovery:
            # expose only ranking time + policy +
            # reconfiguration count.
            elif metric == "reconfiguration":
                allowed = {
                    "time",
                    "policy",
                    "reconfig_count",
                }

            else:
                # Conservative fallback for any future metric.
                allowed = {
                    "time",
                }

            shaped_item = {
                k: cls._operator_evidence(v, query)
                for k, v in item.items()
                if k in allowed
                and k not in hidden
            }

            shaped_intervals.append(
                shaped_item
            )

        shaped["intervals"] = shaped_intervals

        return shaped

    @classmethod
    def _shape_time_range_summary(
        cls,
        value: dict,
        query: str,
        hidden: set[str],
    ) -> dict:
        """Expose bounded range evidence based on the operator's requested scope."""
        q = query.lower()

        shaped: dict = {
            "category": "time_range_summary",
        }

        for key in (
            "start_time",
            "end_time",
        ):
            if key in value:
                shaped[key] = value[key]

        summary = value.get("summary")

        if not isinstance(summary, dict):
            return shaped

        # Core range fields useful for a normal summary.
        core_fields = {
            "interval_count",
            "mean_total_gbps",
            "peak_total_gbps",
            "peak_load_time",
            "highest_risk_time",
            "state_counts",
            "recommendation_counts",
            "objective",
        }

        # Keep range generation on aggregate, already-computed evidence only.
        # Per-policy ratio tables are intentionally withheld because the normal
        # range response does not require the LLM to convert or compare them.
        allowed_fields = set(core_fields)

        shaped_summary = {
            k: cls._operator_evidence(v, query)
            for k, v in summary.items()
            if k in allowed_fields
            and k not in hidden
        }

        shaped["summary"] = shaped_summary

        return shaped