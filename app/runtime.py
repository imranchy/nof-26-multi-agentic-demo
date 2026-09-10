from __future__ import annotations

from typing import Any

from app.agents.coordinator import CoordinatorAgent
from app.agents.explanation import ExplanationAgent
from app.agents.forecast import ForecastAgent
from app.agents.guardrail import GuardrailAgent
from app.agents.sla import SLAAgent
from app.schemas import AgentEvent, AgentResponse, QueryPlan, ToolStep
from app.semantic import SemanticResolver
from app.tools import OperatorTools

class MultiAgentRuntime:
    """Mistral semantic orchestration over prediction and deterministic network tools."""

    def __init__(self, forecast_mode: str = "live", use_llm: bool = True) -> None:
        self.forecast_agent = ForecastAgent(mode=forecast_mode)
        self.sla_agent = SLAAgent()
        self.guardrail = GuardrailAgent()
        forecast = self.forecast_agent.forecast()
        self.frame = self.sla_agent.assess(forecast)
        self.startup_warnings = self.guardrail.validate_frame(self.frame)
        self.tools = OperatorTools(self.frame, forecast_mode=forecast_mode)
        self.coordinator = CoordinatorAgent(use_llm=use_llm)
        self.explainer = ExplanationAgent(self.guardrail)
        self.memory: dict[str, Any] = {}

    def ask(self, query: str) -> AgentResponse:
        trace = [AgentEvent("Coordinator Agent", "Interpreting operator intent with Mistral")]
        proposed = self.coordinator.select_plan(query, self.memory)
        coordinator_audit = dict(self.coordinator.last_audit)
        raw_proposed = [] if coordinator_audit.get("fallback_used") else [
            {"tool": name, "arguments": dict(arguments)} for name, arguments in proposed
        ]

        proposed, correction = self._guard_plan(query, proposed)
        if correction:
            trace.append(AgentEvent("Deterministic Routing Guardrail", correction, status="corrected"))

        executed_steps: list[ToolStep] = []
        step_evidence: list[dict[str, Any]] = []
        fallbacks: list[str] = []

        for index, (tool_name, arguments) in enumerate(proposed, start=1):
            tool_name = self._normalize_decline_route(query, tool_name)
            args = self._normalize_tool_arguments(query, tool_name, arguments)
            trace.append(AgentEvent("Coordinator Agent", f"Step {index}: selected {tool_name}", detail=str(args)))
            evidence, fallback = self.tools.execute(tool_name, args, self.memory)
            trace.append(AgentEvent(self._tool_agent_name(tool_name), f"Executed {tool_name}"))
            executed_steps.append(ToolStep(tool_name=tool_name, arguments=args))
            step_evidence.append(evidence)
            fallbacks.append(fallback)
            self._update_memory(tool_name, args, evidence)

        combined = self._combine_evidence(step_evidence)
        fallback = " ".join(dict.fromkeys(fallbacks))
        explanation = self.explainer.explain(query, combined, fallback)
        trace.append(AgentEvent(
            "Grounding Guardrail",
            "Accepted Mistral explanation" if explanation.grounding_passed else "Used deterministic fallback",
            status="completed" if explanation.grounding_passed else "fallback",
            detail=", ".join(explanation.issues),
        ))

        history_steps = [{"tool": s.tool_name, "arguments": s.arguments} for s in executed_steps]
        self.coordinator.record_turn(query, history_steps, combined, explanation.accepted_answer)
        primary = executed_steps[-1]
        return AgentResponse(
            answer=explanation.accepted_answer,
            raw_llm_answer=explanation.raw_answer,
            plan=QueryPlan(
                intent=str(combined.get("category", primary.tool_name)),
                tool_name=primary.tool_name,
                arguments=primary.arguments,
                steps=executed_steps,
            ),
            evidence=combined,
            grounding_passed=explanation.grounding_passed,
            grounding_issues=explanation.issues,
            warnings=list(self.startup_warnings),
            trace=trace,
            routing_audit={
                "mistral_proposed": raw_proposed,
                "executed": history_steps,
                "deterministic_correction": correction,
                "coordinator": coordinator_audit,
            },
        )

    def execute_tool_direct(self, tool_name: str, arguments: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
        return self.tools.execute(tool_name, arguments or {}, self.memory)

    def reset(self) -> None:
        self.coordinator.reset()
        self.memory.clear()

    def _guard_plan(self, query: str, proposed: list[tuple[str, dict[str, Any]]]) -> tuple[list[tuple[str, dict[str, Any]]], str | None]:
        q = query.lower()
        # One useful compound workflow in v1: find a risky interval then compare policies there.
        if any(x in q for x in ("highest-risk", "highest risk", "riskiest", "worst interval")) and any(x in q for x in ("recommend", "which policy", "compare policies", "best policy")):
            desired = [("find_risk_intervals", {}), ("compare_policies_at_time", {})]
            if [name for name, _ in proposed] != [name for name, _ in desired]:
                return desired, "Corrected the plan to the bounded risk-discovery then policy-comparison workflow."
            return proposed, None

        forced = SemanticResolver.high_confidence_tool(
            query,
            self.memory,
        )

        if not forced:
            return proposed, None

        if (
            len(proposed) == 1
            and proposed[0][0] == forced
        ):
            return proposed, None

        # This also safely handles an empty or over-decomposed Mistral plan.
        return [
            (forced, {})
        ], (
            f"Corrected an incompatible Mistral route to {forced} "
            "based on explicit operator language."
        )

    def _normalize_tool_arguments(self, query: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        args = dict(arguments)
        default_objective = self.tools.recommendation_cfg["default_objective"]

        single_time_tools = {
            "get_traffic_forecast", "get_sla_prediction", "get_network_state_at_time", "explain_sla_risk",
            "compare_policies_at_time", "simulate_policy_at_time", "analyze_constrained_allocation",
        }
        if tool_name in single_time_tools:
            proposed = args.get("time")
            resolved = SemanticResolver.normalize_time(query, str(proposed) if proposed else None, self.memory)
            if resolved:
                args["time"] = resolved
            elif self.memory.get("last_time"):
                args["time"] = self.memory["last_time"]
            else:
                args["time"] = self.tools._resolve_time({}, self.memory)

        if tool_name == "compare_network_states":
            explicit = SemanticResolver.explicit_times(query)

            if len(explicit) >= 2:
                # Explicit query timestamps always override Mistral-proposed
                # timestamps and previous conversation context.
                args["time_a"] = explicit[0]
                args["time_b"] = explicit[1]

            else:
                time_a = args.get("time_a")
                time_b = args.get("time_b")

                if not time_a:
                    time_a = self.memory.get("comparison_time_a")

                if not time_b:
                    time_b = self.memory.get("last_time")

                if time_a:
                    args["time_a"] = str(time_a)

                if time_b:
                    args["time_b"] = str(time_b)

            args.setdefault(
                "policy",
                self.memory.get("recommended_policy")
                or self.tools.controller["active_policy"],
            )

        if tool_name == "summarize_time_range":
            explicit = SemanticResolver.explicit_times(query)
            if len(explicit) >= 2:
                args["start_time"], args["end_time"] = explicit[-2], explicit[-1]
            args["objective"] = SemanticResolver.normalize_objective(query, args.get("objective"), default_objective)

        if tool_name in {"compare_policies_at_time", "analyze_constrained_allocation"}:
            args["objective"] = SemanticResolver.normalize_objective(query, args.get("objective"), default_objective)

        if tool_name == "explain_sla_risk":
            claimed = SemanticResolver.claimed_sla_state(query)
            if claimed:
                args["claimed_state"] = claimed

        if tool_name == "simulate_policy_at_time":
            explicit_policy = SemanticResolver.extract_policy(query)
            if explicit_policy:
                args["policy"] = explicit_policy
            else:
                args.setdefault("policy", self.memory.get("recommended_policy") or self.memory.get("last_policy") or self.tools.controller["active_policy"])

        if tool_name == "analyze_constrained_allocation":
            extracted = SemanticResolver.extract_constraints(query)
            constraint_keys = {"enterprise_subcarriers", "ran_subcarriers", "pon_subcarriers"}
            proposed_constraints = {k: v for k, v in args.items() if k in constraint_keys and v is not None}
            current = {**proposed_constraints, **extracted}
            q = query.lower()
            if any(token in q for token in ("also", "in addition", "as well", "and keep", "and give")):
                current = {**self.memory.get("last_constraints_raw", {}), **current}
            for key in constraint_keys:
                args.pop(key, None)
            args.update(current)
            args.setdefault("reference_policy", self.memory.get("recommended_policy") or self.tools.controller["active_policy"])

        if tool_name == "get_network_state_at_time":
            explicit_policy = SemanticResolver.extract_policy(query)
            args["policy"] = explicit_policy or args.get("policy") or self.tools.controller["active_policy"]

        if tool_name == "find_risk_intervals":
            q = query.lower()
            if any(x in q for x in ("busiest", "peak load", "highest load")):
                args["metric"] = "total_gbps"
            elif "blocking" in q:
                args["metric"] = "blocking"
            elif "reconfig" in q or "churn" in q:
                args["metric"] = "reconfiguration"
            else:
                args["metric"] = "failure_probability"
            # Extract a requested top-k when phrased with a small integer, otherwise 3.
            import re
            match = re.search(r"\b(?:top|three|two|five|first)\s*(\d+)?", q)
            if args.get("top_k") is None:
                args["top_k"] = 3

        return {k: v for k, v in args.items() if v is not None}

    @staticmethod
    def _normalize_decline_route(query: str, tool_name: str) -> str:
        if tool_name not in {"decline_physical_layer", "decline_out_of_scope"}:
            return tool_name
        q = query.lower()
        physical = any(term in q for term in (
            "osnr", "ber", "q-factor", "q factor", "fiber cut", "fibre cut", "optical impairment",
            "physical layer", "physical-layer", "gnpy", "rx power", "launch power",
        ))
        return "decline_physical_layer" if physical else "decline_out_of_scope"

    def _update_memory(self, tool_name: str, args: dict[str, Any], evidence: dict[str, Any]) -> None:
        if evidence.get("timestamp"):
            self.memory["last_time"] = evidence["timestamp"]
        if evidence.get("time_a"):
            self.memory["comparison_time_a"] = evidence["time_a"]
        if evidence.get("time_b"):
            self.memory["comparison_time_b"] = evidence["time_b"]
            self.memory["last_time"] = evidence["time_b"]
        if tool_name == "find_risk_intervals" and evidence.get("intervals"):
            self.memory["last_time"] = evidence["intervals"][0]["time"]
        recommended = evidence.get("recommended_policy")
        if recommended:
            self.memory["recommended_policy"] = recommended
            self.memory["last_policy"] = recommended
        for key in ("policy", "displayed_policy"):
            if evidence.get(key):
                self.memory["last_policy"] = evidence[key]
        if tool_name == "analyze_constrained_allocation":
            raw = {k: int(v) for k, v in args.items() if k in {"enterprise_subcarriers", "ran_subcarriers", "pon_subcarriers"}}
            self.memory["last_constraints_raw"] = raw
            self.memory["last_constraints"] = evidence.get("operator_constraints", {})
            self.memory["last_reference_policy"] = evidence.get("reference_policy")
            self.memory["last_objective"] = evidence.get("objective")
        self.memory["last_tool"] = tool_name
        self.memory["last_result"] = evidence

    @staticmethod
    def _combine_evidence(items: list[dict[str, Any]]) -> dict[str, Any]:
        if len(items) == 1:
            return items[0]
        return {"category": "multi_tool_analysis", "tool_count": len(items), "steps": items, "final": items[-1]}

    @staticmethod
    def _tool_agent_name(tool_name: str) -> str:
        if tool_name == "get_traffic_forecast":
            return "Traffic Prediction Capability"
        if tool_name in {"get_sla_prediction", "explain_sla_risk"}:
            return "SLA Risk Capability"
        if tool_name in {"compare_policies_at_time", "simulate_policy_at_time", "analyze_constrained_allocation"}:
            return "PSC Policy Engine"
        return 