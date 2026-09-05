from __future__ import annotations

from typing import Any

import pandas as pd

from app.agents.coordinator import CoordinatorAgent
from app.agents.diagnosis import DiagnosisAgent
from app.agents.explanation import ExplanationAgent
from app.agents.forecast import ForecastAgent
from app.agents.guardrail import GuardrailAgent
from app.agents.recovery import RecoveryAgent
from app.agents.sla import SLAAgent
from app.schemas import AgentEvent, AgentResponse, QueryPlan


TOOL_TO_INTENT = {
    "summarize_day_ahead": "network_summary",
    "find_next_sla_risk": "next_risk",
    "find_highest_risk": "highest_risk",
    "find_service_peak": "service_peak",
    "rank_service_intervals": "top_service_intervals",
    "diagnose_highest_risk": "service_contribution",
    "recommend_subcarrier_allocation": "recovery",
    "check_allocation_feasibility": "recovery",
    "compare_service_loads": "compare_services",
    "get_state_distribution": "state_distribution",
    "validate_forecast": "validate",
    "decline_out_of_scope": "out_of_scope",
}


class MultiAgentRuntime:
    """Connect Mistral tool selection to deterministic specialist agents."""

    def __init__(self, forecast_mode: str = "prepared", use_llm: bool = True) -> None:
        self.coordinator = CoordinatorAgent(use_llm=use_llm)
        self.forecaster = ForecastAgent(mode=forecast_mode)
        self.sla = SLAAgent()
        self.recovery = RecoveryAgent()
        self.guardrail = GuardrailAgent()
        self.diagnosis = DiagnosisAgent()
        self.explanation = ExplanationAgent()
        self.frame = self._prepare()
        self._last_fallback = ""

    def _prepare(self) -> pd.DataFrame:
        forecast = self.forecaster.forecast()
        assessed = self.sla.assess(forecast)
        recovered = self.recovery.recommend(assessed)
        self.startup_warnings = self.guardrail.validate(recovered)
        return recovered

    def ask(self, query: str) -> AgentResponse:
        trace = [
            AgentEvent(
                "Coordinator Agent",
                "Asked Mistral to select one analytical tool",
                detail="schema-constrained Mistral tool selection",
            )
        ]
        candidate, tool_name, arguments, evidence = self.coordinator.run(
            query, lambda name, args: self._execute_tool(name, args, trace)
        )
        plan = self._plan_for(tool_name, arguments)
        warnings = list(evidence.get("warnings", []))

        # The LLM writes the response, but deterministic checks reject invented
        # numbers, wrong units, or probability language for state distributions.
        answer = candidate
        grounded = self.explanation._numbers_are_grounded(candidate, evidence)
        grounded = grounded and self.explanation._semantics_are_grounded(candidate, evidence)
        if not grounded:
            answer = self._last_fallback
            trace.append(
                AgentEvent(
                    "Guardrail Agent",
                    "Rejected an ungrounded generated response",
                    detail="used deterministic evidence rendering",
                )
            )
        else:
            trace.append(
                AgentEvent(
                    "Guardrail Agent",
                    "Validated generated response against tool evidence",
                )
            )
        trace.append(
            AgentEvent(
                "Operator Response Agent",
                "Rendered the grounded Mistral response",
                detail=f"tool={tool_name}",
            )
        )
        return AgentResponse(answer, plan, evidence, warnings, trace)

    def reset_conversation(self) -> None:
        self.coordinator.reset()

    def _execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        trace: list[AgentEvent],
    ) -> dict[str, Any]:
        if name not in TOOL_TO_INTENT:
            raise ValueError(f"Mistral requested unknown tool: {name}")

        trace.extend([
            AgentEvent("Forecast Agent", "Provided the XGBoost day-ahead forecast", detail="288 intervals"),
            AgentEvent("SLA Agent", "Provided Random Forest SLA states and scores"),
        ])

        handlers = {
            "summarize_day_ahead": self._summary,
            "find_next_sla_risk": lambda: self._next_risk(arguments),
            "find_highest_risk": self._highest_risk,
            "find_service_peak": lambda: self._service_peak(arguments, ranked=False),
            "rank_service_intervals": lambda: self._service_peak(arguments, ranked=True),
            "diagnose_highest_risk": lambda: self._diagnose(trace),
            "recommend_subcarrier_allocation": lambda: self._allocation(False, trace),
            "check_allocation_feasibility": lambda: self._allocation(True, trace),
            "compare_service_loads": lambda: self._compare(arguments),
            "get_state_distribution": self._distribution,
            "validate_forecast": self._validation,
            "decline_out_of_scope": self._out_of_scope,
        }
        evidence, fallback = handlers[name]()
        evidence["validation"] = "passed"
        evidence["selected_tool"] = name
        evidence["tool_arguments"] = arguments
        self._last_fallback = fallback
        return evidence

    def _summary(self) -> tuple[dict[str, Any], str]:
        counts = self.frame.predicted_state.value_counts()
        peak = self._peak_row()
        state_counts = {s: int(counts.get(s, 0)) for s in ("normal", "degraded", "failure_prone")}
        percentages = {s: round(100 * count / len(self.frame), 1) for s, count in state_counts.items()}
        evidence = {
            "interval_minutes": 5,
            "intervals": len(self.frame),
            "state_counts": state_counts,
            "state_distribution_percent": percentages,
            "peak_risk": self._row(peak),
            "warnings": list(self.startup_warnings),
        }
        fallback = (
            f"The day-ahead forecast covers {len(self.frame)} five-minute intervals. "
            f"Of these, {state_counts['normal']} ({percentages['normal']:.1f}%) are normal, "
            f"{state_counts['degraded']} ({percentages['degraded']:.1f}%) are degraded, and "
            f"{state_counts['failure_prone']} ({percentages['failure_prone']:.1f}%) are failure-prone. "
            f"The highest Failure-prone score is {peak.failure_probability:.2f} at {peak.time}, "
            f"when total predicted traffic is {peak.total_gbps:.2f} Gbps."
        )
        return evidence, self._with_warnings(fallback, evidence)

    def _next_risk(self, args: dict[str, Any]) -> tuple[dict[str, Any], str]:
        state = str(args.get("state", "any_non_normal"))
        if state not in {"any_non_normal", "degraded", "failure_prone"}:
            raise ValueError("Invalid SLA state")
        candidates = (
            self.frame[self.frame.predicted_state != "normal"]
            if state == "any_non_normal"
            else self.frame[self.frame.predicted_state == state]
        )
        if candidates.empty:
            return {"result": "none", "requested_state": state}, "No matching SLA-risk interval was found."
        row = candidates.sort_values("minute_of_day").iloc[0]
        evidence = {"requested_state": state, "interval": self._row(row)}
        if row.prediction_confidence < 0.60:
            evidence["warnings"] = [f"The selected interval has low classifier confidence ({row.prediction_confidence:.2f})."]
        fallback = (
            f"The first predicted {('non-normal' if state == 'any_non_normal' else state.replace('_', '-'))} "
            f"interval is {row.time}, classified as {str(row.predicted_state).replace('_', '-')}. "
            f"Predicted traffic is Enterprise {row.enterprise_gbps:.2f} Gbps, RAN {row.ran_gbps:.2f} Gbps, "
            f"and PON {row.pon_gbps:.2f} Gbps, totalling {row.total_gbps:.2f} Gbps. "
            f"Its Failure-prone score is {row.failure_probability:.2f} and classifier confidence is "
            f"{row.prediction_confidence:.2f}."
        )
        return evidence, self._with_warnings(fallback, evidence)

    def _highest_risk(self) -> tuple[dict[str, Any], str]:
        row = self._peak_row()
        evidence = {"interval": self._row(row)}
        fallback = (
            f"The highest-risk interval is {row.time}, classified as "
            f"{str(row.predicted_state).replace('_', '-')}. Total predicted traffic is "
            f"{row.total_gbps:.2f} Gbps, the Failure-prone score is {row.failure_probability:.2f}, "
            f"and classifier confidence is {row.prediction_confidence:.2f}."
        )
        return evidence, fallback

    def _service_peak(self, args: dict[str, Any], ranked: bool) -> tuple[dict[str, Any], str]:
        service = self._service(args)
        top_k = max(1, min(int(args.get("top_k", 5)), 20)) if ranked else 1
        top = self.frame.nlargest(top_k, f"{service}_gbps")
        intervals = [
            {"time": row.time, "service_load_gbps": round(float(row[f"{service}_gbps"]), 2)}
            for _, row in top.iterrows()
        ]
        evidence = {"service": service.upper(), "top_k": top_k, "intervals": intervals}
        if ranked:
            entries = "; ".join(f"{item['time']}: {item['service_load_gbps']:.2f} Gbps" for item in intervals)
            fallback = f"Top {top_k} {service.upper()} demand intervals: {entries}."
        else:
            fallback = f"{service.upper()} traffic peaks at {intervals[0]['time']} with {intervals[0]['service_load_gbps']:.2f} Gbps."
        return evidence, fallback

    def _diagnose(self, trace: list[AgentEvent]) -> tuple[dict[str, Any], str]:
        row = self._peak_row()
        position = self.frame.index.get_loc(row.name)
        previous = self.frame.iloc[position - 1] if position > 0 else None
        diagnosis = self.diagnosis.diagnose(row, previous)
        trace.append(AgentEvent("Diagnosis Agent", "Calculated the dominant service and interval change"))
        evidence = {"interval": self._row(row), "diagnosis": diagnosis}
        fallback = (
            f"At the highest-risk interval, {row.time}, {diagnosis['dominant_service']} is dominant at "
            f"{diagnosis['dominant_load_gbps']:.2f} Gbps, representing "
            f"{diagnosis['dominant_share_percent']:.1f}% of the total {row.total_gbps:.2f} Gbps load. "
            f"The interval is {str(row.predicted_state).replace('_', '-')} with classifier confidence "
            f"{row.prediction_confidence:.2f}."
        )
        return evidence, fallback

    def _allocation(self, feasibility_only: bool, trace: list[AgentEvent]) -> tuple[dict[str, Any], str]:
        row = self._peak_row()
        recommendation = {
            "observed_policy": "priority_trf",
            "allocation": {
                "enterprise_subcarriers": int(row.candidate_enterprise_subcarriers),
                "pon_subcarriers": int(row.candidate_pon_subcarriers),
                "ran_subcarriers": int(row.candidate_ran_subcarriers),
            },
            "capacity_gbps": {
                "enterprise": float(row.candidate_enterprise_capacity_gbps),
                "pon": float(row.candidate_pon_capacity_gbps),
                "ran": float(row.candidate_ran_capacity_gbps),
            },
            "estimated_overflow_gbps": float(row.estimated_overflow_gbps),
            "overflow_services": list(row.overflow_services),
            "allocation_feasible": bool(row.layout_feasible),
            "action": row.recommended_action,
            "operator_approval_required": bool(row.operator_approval_required),
        }
        evidence = {"interval": self._row(row), "recommendation": recommendation}
        trace.append(AgentEvent("Recovery Agent", "Evaluated observed four-subcarrier allocations"))
        cap = recommendation["capacity_gbps"]
        if feasibility_only:
            if recommendation["allocation_feasible"]:
                fallback = (
                    f"Yes. At {row.time}, the suggested allocation accommodates all predicted service traffic "
                    f"with {cap['enterprise']:.0f} Gbps for Enterprise, {cap['pon']:.0f} Gbps for PON, and "
                    f"{cap['ran']:.0f} Gbps for RAN. Operator approval is required."
                )
            else:
                services = ", ".join(recommendation["overflow_services"])
                fallback = (
                    f"No. At {row.time}, the suggested allocation leaves "
                    f"{recommendation['estimated_overflow_gbps']:.2f} Gbps unmet for {services}. "
                    "Additional capacity, traffic offloading, or rerouting is required, subject to operator approval."
                )
        else:
            alloc = recommendation["allocation"]
            services = ", ".join(recommendation["overflow_services"])
            fallback = (
                f"At {row.time}, the minimum-overflow allocation assigns {alloc['enterprise_subcarriers']} "
                f"subcarrier to Enterprise, {alloc['pon_subcarriers']} to PON, and {alloc['ran_subcarriers']} "
                f"to RAN, providing {cap['enterprise']:.0f}, {cap['pon']:.0f}, and {cap['ran']:.0f} Gbps "
                f"respectively. It leaves {recommendation['estimated_overflow_gbps']:.2f} Gbps unmet for "
                f"{services}. This is advisory and requires operator approval."
            )
        return evidence, fallback

    def _compare(self, args: dict[str, Any]) -> tuple[dict[str, Any], str]:
        statistic = str(args.get("statistic", "mean"))
        if statistic not in {"mean", "maximum"}:
            raise ValueError("Invalid comparison statistic")
        reducer = "mean" if statistic == "mean" else "max"
        values = {s.upper(): round(float(getattr(self.frame[f"{s}_gbps"], reducer)()), 2) for s in ("enterprise", "ran", "pon")}
        evidence = {"statistic": statistic, "service_load_gbps": values}
        fallback = f"Daily {statistic} loads are " + ", ".join(f"{key} {value:.2f} Gbps" for key, value in values.items()) + "."
        return evidence, fallback

    def _distribution(self) -> tuple[dict[str, Any], str]:
        counts = self.frame.predicted_state.value_counts()
        values = {
            state: {"count": int(counts.get(state, 0)), "percent": round(100 * int(counts.get(state, 0)) / len(self.frame), 1)}
            for state in ("normal", "degraded", "failure_prone")
        }
        evidence = {"intervals": len(self.frame), "states": values}
        fallback = "SLA-state distribution: " + ", ".join(
            f"{state.replace('_', '-')} {value['count']} ({value['percent']:.1f}%)" for state, value in values.items()
        ) + "."
        return evidence, fallback

    def _validation(self) -> tuple[dict[str, Any], str]:
        evidence = {
            "status": "passed",
            "checked_intervals": len(self.frame),
            "checks": ["schema", "non-negative traffic", "aggregate-total consistency", "class scores", "timestamps"],
            "warnings": list(self.startup_warnings),
        }
        fallback = f"Guardrail validation passed across {len(self.frame)} forecast intervals."
        return evidence, self._with_warnings(fallback, evidence)

    def _out_of_scope(self) -> tuple[dict[str, Any], str]:
        evidence = {
            "result": "out_of_scope",
            "supported_topics": ["network traffic forecasts", "SLA-risk detection", "service diagnosis", "subcarrier allocation", "recovery recommendations"],
        }
        return evidence, "I can only assist with network traffic forecasts, SLA-risk detection, service diagnosis, subcarrier allocation, and recovery recommendations."

    def _peak_row(self) -> pd.Series:
        return self.frame.loc[self.frame.failure_probability.idxmax()]

    @staticmethod
    def _service(args: dict[str, Any]) -> str:
        service = str(args.get("service", "")).lower()
        if service not in {"enterprise", "ran", "pon"}:
            raise ValueError("Service must be enterprise, ran, or pon")
        return service

    @staticmethod
    def _row(row: pd.Series) -> dict[str, Any]:
        return {
            "time": row.time,
            "state": row.predicted_state,
            "enterprise_gbps": round(float(row.enterprise_gbps), 2),
            "ran_gbps": round(float(row.ran_gbps), 2),
            "pon_gbps": round(float(row.pon_gbps), 2),
            "total_gbps": round(float(row.total_gbps), 2),
            "failure_prone_score": round(float(row.failure_probability), 2),
            "classifier_confidence": round(float(row.prediction_confidence), 2),
        }

    @staticmethod
    def _with_warnings(text: str, evidence: dict[str, Any]) -> str:
        warnings = evidence.get("warnings", [])
        return text + ((" Warning: " + " ".join(warnings)) if warnings else "")

    @staticmethod
    def _plan_for(tool_name: str, args: dict[str, Any]) -> QueryPlan:
        state = args.get("state")
        return QueryPlan(
            intent=TOOL_TO_INTENT[tool_name],
            service=args.get("service"),
            state=None if state == "any_non_normal" else state,
            top_k=int(args.get("top_k", 1)),
            needs_recovery=tool_name in {"recommend_subcarrier_allocation", "check_allocation_feasibility"},
            needs_diagnosis=tool_name == "diagnose_highest_risk",
            source="mistral-tool-call",
        )
