from __future__ import annotations

from typing import Any

from app.agents.explanation import ExplanationAgent
from app.agents.forecast import ForecastAgent
from app.agents.guardrail import GuardrailAgent
from app.agents.sla import SLAAgent
from app.agents.specialist import LocalSpecialistAgent
from app.agents.tool_catalog import ALL_TOOL_NAMES, argument_names
from app.schemas import AgentEvent, AgentResponse, QueryPlan, ToolStep
from app.semantic import SemanticResolver
from app.state_manager import ConversationStateManager
from app.tools import OperatorTools


class MultiAgentRuntime:
    """Direct Mistral tool routing over deterministic network capabilities.

    Mistral owns natural-language understanding, multilingual context handling,
    clarification decisions, tool selection, and explicit argument extraction.
    Python owns only deterministic state resolution, arithmetic, validation,
    network/ML execution, and grounding safety.
    """

    TOOL_ARGUMENTS = {name: argument_names(name) for name in ALL_TOOL_NAMES}

    def __init__(self, forecast_mode: str = "live", use_llm: bool = True) -> None:
        self.forecast_agent = ForecastAgent(mode=forecast_mode)
        self.sla_agent = SLAAgent()
        self.guardrail = GuardrailAgent()
        forecast = self.forecast_agent.forecast()
        self.frame = self.sla_agent.assess(forecast)
        self.startup_warnings = self.guardrail.validate_frame(self.frame)
        self.tools = OperatorTools(self.frame, forecast_mode=forecast_mode)
        self.router = LocalSpecialistAgent(use_llm=use_llm)
        # Backward-compatible alias for callers/tests that referenced specialist.
        self.specialist = self.router
        self.explainer = ExplanationAgent(self.guardrail)
        self.memory: dict[str, Any] = {}
        self.history: list[dict[str, Any]] = []
        self.state_manager = ConversationStateManager()

    def ask(self, query: str) -> AgentResponse:
        trace = [AgentEvent("Mistral Tool Router", "Selecting one analytical capability from the full local tool catalog")]
        state = self.state_manager.compact_state(self.memory)

        try:
            tool_name, raw_arguments = self.router.select_tool(
                query=query,
                context_memory=state,
                conversation_history=self.history,
            )
            router_audit = dict(self.router.last_audit)
        except Exception as exc:
            router_audit = dict(self.router.last_audit)
            router_audit.setdefault("mode", "ollama_native_tool_calling")
            router_audit["parse_failed"] = True
            router_audit["fallback_used"] = True
            router_audit["error"] = f"{type(exc).__name__}: {exc}"
            return self._router_failure_response(query, router_audit, trace)

        trace.append(AgentEvent("Mistral Tool Router", f"Selected {tool_name}"))

        if tool_name == "request_clarification":
            return self._clarification_response(query, raw_arguments, router_audit, trace)

        try:
            args = self._normalize_tool_arguments(tool_name, raw_arguments, state)
            trace.append(AgentEvent("Deterministic Validation", "Validated and resolved tool arguments", detail=str(args)))
            evidence, fallback = self.tools.execute(tool_name, args, self.memory)
        except Exception as exc:
            return self._tool_validation_failure_response(
                query=query,
                tool_name=tool_name,
                raw_arguments=raw_arguments,
                error=exc,
                router_audit=router_audit,
                trace=trace,
            )

        trace.append(AgentEvent(self._tool_agent_name(tool_name), f"Executed {tool_name}"))
        self._update_memory(tool_name, args, evidence)

        explanation = self.explainer.explain(query, evidence, fallback)
        trace.append(AgentEvent(
            "Grounding Guardrail",
            "Accepted Mistral explanation" if explanation.grounding_passed else "Used deterministic fallback",
            status="completed" if explanation.grounding_passed else "fallback",
            detail=", ".join(explanation.issues),
        ))

        self._record_turn(query, tool_name, args, evidence, explanation.accepted_answer)
        executed_steps = [ToolStep(tool_name=tool_name, arguments=args)]

        return AgentResponse(
            answer=explanation.accepted_answer,
            raw_llm_answer=explanation.raw_answer,
            plan=QueryPlan(
                intent=str(evidence.get("category", tool_name)),
                tool_name=tool_name,
                arguments=args,
                steps=executed_steps,
                source="mistral-direct-tool-calling",
            ),
            evidence=evidence,
            grounding_passed=explanation.grounding_passed,
            grounding_issues=explanation.issues,
            warnings=list(self.startup_warnings),
            trace=trace,
            routing_audit={
                "mistral_proposed": [{"tool": tool_name, "arguments": dict(raw_arguments)}],
                "tool_router": router_audit,
                "executed": [{"tool": tool_name, "arguments": args}],
                "deterministic_correction": self._argument_resolution_changed(raw_arguments, args),
                "tool_calling_mode": router_audit.get(
                "mode",
                "ollama_native_tool_calling",
                ),
            },
        )

    def _normalize_tool_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        raw_input = dict(arguments)
        allowed = self.TOOL_ARGUMENTS.get(tool_name, set())

        # Preserve legacy scalar SC constraints for internal callers/tests.
        # These keys are intentionally not exposed in the Mistral-facing schema.
        legacy_constraint_input = {
            key: value
            for key, value in raw_input.items()
            if key in SemanticResolver.CONSTRAINT_KEYS and value is not None
        }

        args = {
            key: value
            for key, value in raw_input.items()
            if key in allowed and value is not None
        }
        default_objective = self.tools.recommendation_cfg["default_objective"]

        single_time_tools = {
            "get_traffic_forecast",
            "get_sla_prediction",
            "get_network_state_at_time",
            "explain_sla_risk",
            "compare_policies_at_time",
            "simulate_policy_at_time",
            "analyze_constrained_allocation",
        }

        if tool_name in single_time_tools:
            relative_offset = args.pop("relative_time_offset_minutes", None)
            explicit_time = SemanticResolver.normalize_time_value(args.get("time"))

            if relative_offset is not None:
                try:
                    offset = int(relative_offset)
                except (TypeError, ValueError) as exc:
                    raise ValueError("relative_time_offset_minutes must be an integer") from exc
                if not -1440 <= offset <= 1440:
                    raise ValueError("relative_time_offset_minutes is out of bounds")

                if offset == 0 and explicit_time is not None:
                    args["time"] = explicit_time
                else:
                    base_time = SemanticResolver.normalize_time_value(state.get("last_time"))
                    if base_time is None:
                        raise ValueError("A relative-time request requires a previous reference time.")
                    args["time"] = self.state_manager.apply_relative_minutes(base_time, offset)
            elif explicit_time is not None:
                args["time"] = explicit_time
            else:
                inherited_time = SemanticResolver.normalize_time_value(state.get("last_time"))
                if inherited_time is None:
                    raise ValueError("A timestamp is required for this operation.")
                args["time"] = inherited_time

        if tool_name == "compare_network_states":
            time_a = SemanticResolver.normalize_time_value(args.get("time_a"))
            time_b = SemanticResolver.normalize_time_value(args.get("time_b"))
            if time_a is None:
                time_a = SemanticResolver.normalize_time_value(state.get("comparison_time_a"))
            if time_b is None:
                time_b = SemanticResolver.normalize_time_value(state.get("comparison_time_b") or state.get("last_time"))
            if time_a is None or time_b is None:
                raise ValueError("Two valid timestamps are required for network-state comparison.")
            args["time_a"] = time_a
            args["time_b"] = time_b
            args["policy"] = (
                SemanticResolver.normalize_policy(args.get("policy"))
                or SemanticResolver.normalize_policy(state.get("recommended_policy"))
                or SemanticResolver.normalize_policy(state.get("last_policy"))
                or str(self.tools.controller["active_policy"]).upper()
            )

        if tool_name == "summarize_time_range":
            start_time = SemanticResolver.normalize_time_value(args.get("start_time"))
            end_time = SemanticResolver.normalize_time_value(args.get("end_time"))
            if start_time is None or end_time is None:
                raise ValueError("A valid start_time and end_time are required.")
            args["start_time"] = start_time
            args["end_time"] = end_time
            args["objective"] = SemanticResolver.normalize_objective_value(
                args.get("objective") or state.get("last_objective"), default_objective
            )

        if tool_name in {"compare_policies_at_time", "analyze_constrained_allocation"}:
            args["objective"] = SemanticResolver.normalize_objective_value(
                args.get("objective") or state.get("last_objective"), default_objective
            )

        if tool_name == "explain_sla_risk":
            claimed = SemanticResolver.normalize_claimed_state(args.get("claimed_state"))
            if claimed is not None:
                args["claimed_state"] = claimed
            else:
                args.pop("claimed_state", None)

        if tool_name == "simulate_policy_at_time":
            policy = (
                SemanticResolver.normalize_policy(args.get("policy"))
                or SemanticResolver.normalize_policy(state.get("recommended_policy"))
                or SemanticResolver.normalize_policy(state.get("last_policy"))
            )
            if policy is None:
                raise ValueError("A policy is required for a policy counterfactual.")
            args["policy"] = policy

        if tool_name == "analyze_constrained_allocation":
            raw_constraints = args.pop("constraints", [])
            if raw_constraints is None:
                raw_constraints = []
            if not isinstance(raw_constraints, list):
                raise ValueError("constraints must be a list")

            current_constraints: dict[str, int] = {}
            service_to_key = {
                "enterprise": "enterprise_subcarriers",
                "ran": "ran_subcarriers",
                "pon": "pon_subcarriers",
            }

            for item in raw_constraints:
                if not isinstance(item, dict):
                    raise ValueError("Each SC constraint must be an object.")
                service = str(item.get("service", "")).strip().lower()
                if service not in service_to_key:
                    raise ValueError(f"Unsupported constrained service: {service!r}")
                try:
                    subcarriers = int(item["subcarriers"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        "Each SC constraint requires an integer subcarriers value."
                    ) from exc
                if not 0 <= subcarriers <= 4:
                    raise ValueError("SC constraint must be between 0 and 4.")
                key = service_to_key[service]
                if key in current_constraints:
                    raise ValueError(f"Duplicate SC constraint for {service}.")
                current_constraints[key] = subcarriers

            # Backward-compatible deterministic path for existing internal callers/tests.
            # Mistral never sees these scalar keys in the tool schema.
            legacy_constraints = SemanticResolver.normalize_constraints(
                legacy_constraint_input
            )
            current_constraints = {
                **legacy_constraints,
                **current_constraints,
            }

            previous_constraints = self.state_manager.memory_for_constraints(state)
            merged_constraints = {**previous_constraints, **current_constraints}
            if not merged_constraints:
                raise ValueError(
                    "At least one explicit or inherited SC-count constraint is required."
                )

            args.update(merged_constraints)
            args["reference_policy"] = (
                SemanticResolver.normalize_policy(args.get("reference_policy"))
                or SemanticResolver.normalize_policy(state.get("last_reference_policy"))
                or SemanticResolver.normalize_policy(state.get("recommended_policy"))
                or SemanticResolver.normalize_policy(state.get("last_policy"))
                or str(self.tools.controller["active_policy"]).upper()
            )

        if tool_name == "get_network_state_at_time":
            args["policy"] = (
                SemanticResolver.normalize_policy(args.get("policy"))
                or SemanticResolver.normalize_policy(state.get("last_policy"))
                or str(self.tools.controller["active_policy"]).upper()
            )

        if tool_name == "find_risk_intervals":
            args["metric"] = SemanticResolver.normalize_metric(args.get("metric"))
            args["top_k"] = SemanticResolver.normalize_top_k(args.get("top_k"), default=3)

        return {k: v for k, v in args.items() if v is not None}

    def _router_failure_response(
        self,
        query: str,
        router_audit: dict[str, Any],
        trace: list[AgentEvent],
    ) -> AgentResponse:
        trace.append(AgentEvent(
            "Mistral Tool Router",
            "Could not obtain a valid function call",
            status="fallback",
            detail=str(router_audit.get("error", "tool-call parse failure")),
        ))
        answer = (
            "I could not safely map that request to one supported network operation. "
            "Please restate the request with the desired analysis and any required time or policy."
        )
        return AgentResponse(
            answer=answer,
            raw_llm_answer=None,
            plan=QueryPlan(intent="routing_failure", tool_name="decline_out_of_scope", arguments={}, steps=[]),
            evidence={"category": "generic_out_of_scope", "reason": "tool_router_failure"},
            grounding_passed=True,
            grounding_issues=[],
            warnings=list(self.startup_warnings),
            trace=trace,
            routing_audit={
                "mistral_proposed": [],
                "tool_router": router_audit,
                "executed": [],
                "deterministic_correction": None,
                "tool_calling_mode": "ollama_native_tool_calling",
            },
        )

    def _clarification_response(
        self,
        query: str,
        raw_arguments: dict[str, Any],
        router_audit: dict[str, Any],
        trace: list[AgentEvent],
    ) -> AgentResponse:
        missing = str(raw_arguments.get("missing_field") or "required context")
        if missing in {"reference_time", "time"}:
            answer = "Which time should I use as the reference?"
        else:
            answer = f"Please provide the missing {missing.replace('_', ' ')} before I continue."
        trace.append(AgentEvent("Mistral Tool Router", "Requested clarification", status="clarification", detail=missing))
        self._record_turn(query, "request_clarification", raw_arguments, {"category": "clarification_required"}, answer)
        return AgentResponse(
            answer=answer,
            raw_llm_answer=None,
            plan=QueryPlan(intent="clarification_required", tool_name="request_clarification", arguments=dict(raw_arguments), steps=[]),
            evidence={"category": "clarification_required", "missing_field": missing},
            grounding_passed=True,
            grounding_issues=[],
            warnings=list(self.startup_warnings),
            trace=trace,
            routing_audit={
                "mistral_proposed": [{"tool": "request_clarification", "arguments": dict(raw_arguments)}],
                "tool_router": router_audit,
                "executed": [],
                "deterministic_correction": None,
                "tool_calling_mode": "ollama_native_tool_calling",
            },
        )

    def _tool_validation_failure_response(
        self,
        query: str,
        tool_name: str,
        raw_arguments: dict[str, Any],
        error: Exception,
        router_audit: dict[str, Any],
        trace: list[AgentEvent],
    ) -> AgentResponse:
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
                source="mistral-direct-tool-calling",
            ),
            evidence={"category": "clarification_required", "reason": "invalid_tool_arguments", "rejected_tool": tool_name},
            grounding_passed=True,
            grounding_issues=[],
            warnings=list(self.startup_warnings),
            trace=trace,
            routing_audit={
                "mistral_proposed": [{"tool": tool_name, "arguments": dict(raw_arguments)}],
                "tool_router": router_audit,
                "executed": [],
                "deterministic_correction": "rejected_invalid_tool_arguments",
                "tool_calling_mode": "ollama_native_tool_calling",
            },
        )

    def execute_tool_direct(self, tool_name: str, arguments: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
        return self.tools.execute(tool_name, arguments or {}, self.memory)

    def reset(self) -> None:
        self.memory.clear()
        self.history.clear()
        self.router.last_audit = {}

    def _record_turn(
        self,
        query: str,
        tool_name: str,
        arguments: dict[str, Any],
        evidence: dict[str, Any],
        answer: str,
    ) -> None:
        self.history.append({
            "query": query,
            "tool": tool_name,
            "arguments": dict(arguments),
            "evidence": self._compact_evidence(evidence),
            "answer": answer,
        })
        self.history = self.history[-8:]

    @staticmethod
    def _compact_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        keep = {"category", "timestamp", "time_a", "time_b", "recommended_policy", "policy", "objective"}
        return {k: evidence[k] for k in keep if k in evidence}

    @staticmethod
    def _argument_resolution_changed(raw_arguments: dict[str, Any], executed_arguments: dict[str, Any]) -> str | None:
        # A deterministic correction is recorded only when Python had to resolve
        # structured state/arithmetic rather than merely apply configured defaults.
        if "relative_time_offset_minutes" in raw_arguments:
            return "resolved_relative_time"
        return None

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
        if evidence.get("objective"):
            self.memory["last_objective"] = evidence["objective"]

        if tool_name == "analyze_constrained_allocation":
            raw = {k: int(v) for k, v in args.items() if k in SemanticResolver.CONSTRAINT_KEYS}
            self.memory["last_constraints_raw"] = raw
            self.memory["last_constraints"] = evidence.get("operator_constraints", {})
            self.memory["last_reference_policy"] = evidence.get("reference_policy")

        self.memory["last_tool"] = tool_name
        self.memory["last_result"] = evidence

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
        "request_clarification": "Clarification Capability",
        "decline_physical_layer": "Scope Guardrail",
        "decline_out_of_scope": "Scope Guardrail",
    }

    @classmethod
    def _tool_agent_name(cls, tool_name: str) -> str:
        return cls.TOOL_DISPLAY_NAMES.get(tool_name, "Scope Guardrail")
