from __future__ import annotations

from typing import Any

from app.agents.coordinator import CoordinatorAgent
from app.agents.explanation import ExplanationAgent
from app.agents.forecast import ForecastAgent
from app.agents.specialist import LocalSpecialistAgent
from app.agents.local_agents import agent_for_tool
from app.agents.tool_catalog import ALL_TOOL_NAMES, argument_names
from app.agents.guardrail import GuardrailAgent
from app.agents.sla import SLAAgent
from app.schemas import AgentEvent, AgentResponse, QueryPlan, ToolStep
from app.semantic import SemanticResolver
from app.state_manager import ConversationStateManager
from app.tools import OperatorTools


class MultiAgentRuntime:
    """Mistral semantic orchestration over deterministic prediction/network tools."""

    TOOL_ARGUMENTS = {name: argument_names(name) for name in ALL_TOOL_NAMES}



    def __init__(self, forecast_mode: str = "live", use_llm: bool = True) -> None:
        self.forecast_agent = ForecastAgent(mode=forecast_mode)
        self.sla_agent = SLAAgent()
        self.guardrail = GuardrailAgent()
        forecast = self.forecast_agent.forecast()
        self.frame = self.sla_agent.assess(forecast)
        self.startup_warnings = self.guardrail.validate_frame(self.frame)
        self.tools = OperatorTools(self.frame, forecast_mode=forecast_mode)
        self.coordinator = CoordinatorAgent(use_llm=use_llm)
        self.specialist = LocalSpecialistAgent(use_llm=use_llm)
        self.explainer = ExplanationAgent(self.guardrail)
        self.memory: dict[str, Any] = {}
        self.state_manager = ConversationStateManager()

    def ask(self, query: str) -> AgentResponse:
        trace = [AgentEvent("Local Coordinator", "Interpreting multilingual conversational context")]

        # Stage 1: Mistral interprets conversational relation only.
        # Python never inspects operator wording.
        decision = self.coordinator.select_decision(query, self.memory)
        coordinator_audit = dict(self.coordinator.last_audit)

        missing_context = self.state_manager.missing_inherited_fields(decision.context, self.memory)
        if missing_context:
            return self._clarification_response(
                query=query,
                missing_fields=missing_context,
                decision=decision,
                coordinator_audit=coordinator_audit,
                trace=trace,
            )

        context_memory = self.state_manager.scoped_memory(decision.context, self.memory)

        # Stage 2: native Mistral/Ollama function calling chooses exactly one local
        # analytical capability. If intent is explicitly inherited, Python exposes
        # only the previously executed function; this enforces the validated
        # context contract without parsing natural language.
        allowed_tools_override = self._native_tool_scope(decision, context_memory)

        try:
            tool_name, arguments = self.specialist.select_tool(
                query=query,
                context_memory=context_memory,
                conversation_history=self.coordinator.history,
                allowed_tools_override=allowed_tools_override,
            )
            specialist_audit = dict(self.specialist.last_audit)
        except Exception as exc:
            specialist_audit = {
                "mode": "mistral_raw_function_calling",
                "parse_failed": True,
                "fallback_used": True,
                "error": f"{type(exc).__name__}: {exc}",
            }
            tool_name, arguments = "decline_out_of_scope", {}

        agent_name = agent_for_tool(tool_name) or "scope_agent"
        trace.append(AgentEvent("Local Coordinator", f"Native Mistral tool call handed off to {agent_name}"))

        try:
            args = self._normalize_tool_arguments(tool_name, arguments, context_memory)
            trace.append(AgentEvent(agent_name, f"Selected native function {tool_name}", detail=str(args)))
            evidence, fallback = self.tools.execute(tool_name, args, self.memory)
        except Exception as exc:
            return self._tool_validation_failure_response(
                query=query,
                tool_name=tool_name,
                raw_arguments=arguments,
                agent_name=agent_name,
                error=exc,
                coordinator_audit=coordinator_audit,
                specialist_audit=specialist_audit,
                trace=trace,
            )

        trace.append(AgentEvent(self._tool_agent_name(tool_name), f"Executed {tool_name}"))
        self._update_memory(tool_name, args, evidence, agent_name)

        executed_steps = [ToolStep(tool_name=tool_name, arguments=args)]
        explanation = self.explainer.explain(query, evidence, fallback)
        trace.append(AgentEvent(
            "Grounding Guardrail",
            "Accepted Mistral explanation" if explanation.grounding_passed else "Used deterministic fallback",
            status="completed" if explanation.grounding_passed else "fallback",
            detail=", ".join(explanation.issues),
        ))

        history_steps = [{"tool": tool_name, "arguments": args}]
        self.coordinator.record_turn(
            query=query,
            handoffs=[agent_name],
            steps=history_steps,
            evidence=evidence,
            answer=explanation.accepted_answer,
        )

        return AgentResponse(
            answer=explanation.accepted_answer,
            raw_llm_answer=explanation.raw_answer,
            plan=QueryPlan(
                intent=str(evidence.get("category", tool_name)),
                tool_name=tool_name,
                arguments=args,
                steps=executed_steps,
                source="mistral-native-tool-calling",
            ),
            evidence=evidence,
            grounding_passed=explanation.grounding_passed,
            grounding_issues=explanation.issues,
            warnings=list(self.startup_warnings),
            trace=trace,
            routing_audit={
                "mistral_proposed": [{"tool": tool_name, "arguments": dict(arguments), "agent": agent_name}],
                "handoffs": [agent_name],
                "context": coordinator_audit.get("context", {}),
                "specialists": [specialist_audit],
                "executed": history_steps,
                "deterministic_correction": None,
                "coordinator": coordinator_audit,
                "tool_calling_mode": "mistral_raw_function_calling",
            },
        )

    def _tool_validation_failure_response(
        self,
        query: str,
        tool_name: str,
        raw_arguments: dict[str, Any],
        agent_name: str,
        error: Exception,
        coordinator_audit: dict[str, Any],
        specialist_audit: dict[str, Any],
        trace: list[AgentEvent],
    ) -> AgentResponse:
        """Fail safely when a native tool call cannot be validated/executed."""
        trace.append(AgentEvent(
            "Deterministic Validation",
            f"Rejected invalid arguments for {tool_name}",
            status="clarification",
            detail=f"{type(error).__name__}: {error}",
        ))
        answer = "I could not safely resolve the requested parameters. Please restate the time, policy, range, or constraint explicitly."
        return AgentResponse(
            answer=answer,
            raw_llm_answer=None,
            plan=QueryPlan(
                intent="clarification_required",
                tool_name=tool_name,
                arguments=dict(raw_arguments),
                steps=[],
                source="mistral-native-tool-calling",
            ),
            evidence={
                "category": "clarification_required",
                "reason": "invalid_tool_arguments",
                "rejected_tool": tool_name,
            },
            grounding_passed=True,
            grounding_issues=[],
            warnings=list(self.startup_warnings),
            trace=trace,
            routing_audit={
                "mistral_proposed": [{"tool": tool_name, "arguments": dict(raw_arguments), "agent": agent_name}],
                "handoffs": [agent_name],
                "context": coordinator_audit.get("context", {}),
                "specialists": [specialist_audit],
                "executed": [],
                "deterministic_correction": "rejected_invalid_tool_arguments",
                "coordinator": coordinator_audit,
                "tool_calling_mode": "ollama_native",
            },
        )

    @staticmethod
    def _native_tool_scope(decision, context_memory: dict[str, Any]) -> tuple[str, ...] | None:
        """Restrict native function calling only when validated intent is inherited."""
        if (
            decision.context.relation == "followup"
            and "intent" in decision.context.inherit
            and context_memory.get("last_tool")
        ):
            return (str(context_memory["last_tool"]),)
        return None

    def _clarification_response(
        self,
        query: str,
        missing_fields: list[str],
        decision,
        coordinator_audit: dict[str, Any],
        trace: list[AgentEvent],
    ) -> AgentResponse:
        missing = set(missing_fields)
        if missing == {"time"}:
            answer = "Please specify the reference time (HH:MM) for that follow-up."
        else:
            labels = ", ".join(sorted(missing_fields))
            answer = f"Please provide the missing conversational context ({labels}) before I continue."

        trace.append(AgentEvent(
            "Local Coordinator",
            "Requested clarification because referenced structured state is unavailable",
            status="clarification",
            detail=", ".join(sorted(missing_fields)),
        ))

        return AgentResponse(
            answer=answer,
            raw_llm_answer=None,
            plan=QueryPlan(
                intent="clarification_required",
                tool_name="request_clarification",
                arguments={"missing_fields": sorted(missing_fields)},
                steps=[],
            ),
            evidence={
                "category": "clarification_required",
                "missing_fields": sorted(missing_fields),
            },
            grounding_passed=True,
            grounding_issues=[],
            warnings=list(self.startup_warnings),
            trace=trace,
            routing_audit={
                "mistral_proposed": [],
                "handoffs": list(decision.handoffs),
                "context": coordinator_audit.get("context", {}),
                "specialists": [],
                "executed": [],
                "deterministic_correction": None,
                "coordinator": coordinator_audit,
                "clarification_required": True,
            },
        )

    def execute_tool_direct(self, tool_name: str, arguments: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
        return self.tools.execute(tool_name, arguments or {}, self.memory)

    def reset(self) -> None:
        self.coordinator.reset()
        self.memory.clear()

    @staticmethod
    def _normalize_optional_policy(value: Any) -> str | None:
        return SemanticResolver.normalize_policy(value)

    def _normalize_tool_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context_memory: dict[str, Any],
    ) -> dict[str, Any]:
        allowed = self.TOOL_ARGUMENTS.get(tool_name, set())
        args = {k: v for k, v in dict(arguments).items() if k in allowed and v is not None}
        default_objective = self.tools.recommendation_cfg["default_objective"]

        single_time_tools = {
            "get_traffic_forecast", "get_sla_prediction", "get_network_state_at_time",
            "explain_sla_risk", "compare_policies_at_time", "simulate_policy_at_time",
            "analyze_constrained_allocation",
        }
        if tool_name in single_time_tools:
            # A relative-time expression is explicit information from this turn,
            # represented structurally by Mistral and calculated by Python.
            if context_memory.get("relative_time_applied") and context_memory.get("last_time"):
                resolved = str(context_memory["last_time"])
            else:
                resolved = SemanticResolver.normalize_time_value(args.get("time"))
                if resolved is None and context_memory.get("last_time"):
                    resolved = SemanticResolver.normalize_time_value(context_memory["last_time"])
                if resolved is None:
                    resolved = self.tools._resolve_time({}, context_memory)
            args["time"] = resolved

        if tool_name == "compare_network_states":
            time_a = SemanticResolver.normalize_time_value(args.get("time_a"))
            time_b = SemanticResolver.normalize_time_value(args.get("time_b"))
            if time_a is None:
                time_a = SemanticResolver.normalize_time_value(context_memory.get("comparison_time_a"))
            if time_b is None:
                time_b = SemanticResolver.normalize_time_value(
                    context_memory.get("comparison_time_b") or context_memory.get("last_time")
                )
            if time_a is not None:
                args["time_a"] = time_a
            if time_b is not None:
                args["time_b"] = time_b
            args["policy"] = (
                SemanticResolver.normalize_policy(args.get("policy"))
                or SemanticResolver.normalize_policy(context_memory.get("recommended_policy"))
                or SemanticResolver.normalize_policy(context_memory.get("last_policy"))
                or str(self.tools.controller["active_policy"]).upper()
            )

        if tool_name == "summarize_time_range":
            start_time = SemanticResolver.normalize_time_value(args.get("start_time"))
            end_time = SemanticResolver.normalize_time_value(args.get("end_time"))
            if start_time is not None:
                args["start_time"] = start_time
            if end_time is not None:
                args["end_time"] = end_time
            args["objective"] = SemanticResolver.normalize_objective_value(
                args.get("objective") or context_memory.get("last_objective"),
                default_objective,
            )

        if tool_name in {"compare_policies_at_time", "analyze_constrained_allocation"}:
            args["objective"] = SemanticResolver.normalize_objective_value(
                args.get("objective") or context_memory.get("last_objective"),
                default_objective,
            )

        if tool_name == "explain_sla_risk":
            claimed = SemanticResolver.normalize_claimed_state(args.get("claimed_state"))
            if claimed is not None:
                args["claimed_state"] = claimed
            else:
                args.pop("claimed_state", None)

        if tool_name == "simulate_policy_at_time":
            args["policy"] = (
                SemanticResolver.normalize_policy(args.get("policy"))
                or SemanticResolver.normalize_policy(context_memory.get("recommended_policy"))
                or SemanticResolver.normalize_policy(context_memory.get("last_policy"))
                or str(self.tools.controller["active_policy"]).upper()
            )

        if tool_name == "analyze_constrained_allocation":
            current_constraints = SemanticResolver.normalize_constraints(args)
            previous_constraints = self.state_manager.memory_for_constraints(context_memory)
            merged_constraints = {**previous_constraints, **current_constraints}

            for key in SemanticResolver.CONSTRAINT_KEYS:
                args.pop(key, None)
            args.update(merged_constraints)

            args["reference_policy"] = (
                SemanticResolver.normalize_policy(args.get("reference_policy"))
                or SemanticResolver.normalize_policy(context_memory.get("last_reference_policy"))
                or SemanticResolver.normalize_policy(context_memory.get("recommended_policy"))
                or SemanticResolver.normalize_policy(context_memory.get("last_policy"))
                or str(self.tools.controller["active_policy"]).upper()
            )

        if tool_name == "get_network_state_at_time":
            args["policy"] = (
                SemanticResolver.normalize_policy(args.get("policy"))
                or str(self.tools.controller["active_policy"]).upper()
            )

        if tool_name == "find_risk_intervals":
            args["metric"] = SemanticResolver.normalize_metric(args.get("metric"))
            args["top_k"] = SemanticResolver.normalize_top_k(args.get("top_k"), default=3)

        return {k: v for k, v in args.items() if v is not None}

    def _update_memory(self, tool_name: str, args: dict[str, Any], evidence: dict[str, Any], agent_name: str | None = None) -> None:
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

        if evidence.get("objective"):
            self.memory["last_objective"] = evidence["objective"]

        if tool_name == "analyze_constrained_allocation":
            raw = {
                k: int(v) for k, v in args.items()
                if k in SemanticResolver.CONSTRAINT_KEYS
            }
            self.memory["last_constraints_raw"] = raw
            self.memory["last_constraints"] = evidence.get("operator_constraints", {})
            self.memory["last_reference_policy"] = evidence.get("reference_policy")

        self.memory["last_tool"] = tool_name
        if agent_name is not None:
            self.memory["last_agent"] = agent_name
        self.memory["last_result"] = evidence

    @staticmethod
    def _combine_evidence(items: list[dict[str, Any]]) -> dict[str, Any]:
        if len(items) == 1:
            return items[0]
        return {"category": "multi_tool_analysis", "tool_count": len(items), "steps": items, "final": items[-1]}

    TOOL_DISPLAY_NAMES = {
        "get_traffic_forecast": "Traffic Prediction Capability",
        "get_sla_prediction": "SLA Risk Capability",
        "explain_sla_risk": "SLA Risk Capability",
        "compare_policies_at_time": "PSC Policy Engine",
        "simulate_policy_at_time": "PSC Policy Engine",
        "analyze_constrained_allocation": "PSC Policy Engine",
        "compare_network_states": "Network Analysis Capability",
        "summarize_time_range": "Network Analysis Capability",
        "find_risk_intervals": "Network Analysis Capability",
        "get_network_state_at_time": "Network Analysis Capability",
        "decline_physical_layer": "Scope Guardrail",
        "decline_out_of_scope": "Scope Guardrail",
    }

    @classmethod
    def _tool_agent_name(cls, tool_name: str) -> str:
        return cls.TOOL_DISPLAY_NAMES.get(tool_name, "Scope Guardrail")
