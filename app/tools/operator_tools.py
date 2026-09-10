from __future__ import annotations

import json
from collections import Counter
from typing import Any

import pandas as pd

from app import config
from app.policy_engine import PolicyRegistry, PolicySimulator
from app.policy_engine.base import ASSIGNMENT_STATES, IDLE, SERVICES

POLICIES = ("PCA", "MBA", "SAA")


class OperatorTools:
    """Deterministic analytical capabilities exposed to the semantic coordinator."""

    def __init__(self, frame: pd.DataFrame, forecast_mode: str = "live") -> None:
        self.frame = frame.sort_values("minute_of_day").reset_index(drop=True).copy()
        self.registry = PolicyRegistry.load()
        self.simulator = PolicySimulator(self.frame, self.registry)
        self.network = config.network_parameters()
        self.controller = config.controller_parameters()
        self.recommendation_cfg = config.load_yaml("recommendation.yaml")["recommendation"]
        self.operator_policy = config.load_yaml("operator_policy.yaml")["operator_policy"]
        self.model_cfg = config.load_yaml("model.yaml")
        self.forecast_mode = forecast_mode

    @staticmethod
    def _policy_or_default(value: Any, default: Any) -> str:
        """Return a valid explicit policy or the supplied default."""
        if value is None:
            return str(default).upper()

        normalized = str(value).strip().upper()

        default_aliases = {
            "",
            "NONE",
            "NULL",
            "N/A",
            "NA",
            "UNSPECIFIED",
            "ACTIVE",
            "ACTIVE-POLICY",
            "ACTIVE_POLICY",
            "CURRENT",
            "CURRENT-POLICY",
            "CURRENT_POLICY",
            "DEFAULT",
        }

        if normalized in default_aliases:
            return str(default).strip().upper()

        return normalized

    def execute(self, name: str, arguments: dict[str, Any], memory: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
        memory = memory or {}
        dispatch = {
            "get_traffic_forecast": self.get_traffic_forecast,
            "get_sla_prediction": self.get_sla_prediction,
            "get_network_state_at_time": self.get_network_state_at_time,
            "explain_sla_risk": self.explain_sla_risk,
            "compare_policies_at_time": self.compare_policies_at_time,
            "simulate_policy_at_time": self.simulate_policy_at_time,
            "analyze_constrained_allocation": self.analyze_constrained_allocation,
            "compare_network_states": self.compare_network_states,
            "find_risk_intervals": self.find_risk_intervals,
            "summarize_time_range": self.summarize_time_range,
            "explain_recommendation_change": self.explain_recommendation_change,
            "summarize_policy_history": self.summarize_policy_history,
            "get_evidence_confidence": self.get_evidence_confidence,
            "validate_recommendation": self.validate_recommendation,
            "analyze_network": self.analyze_network,
            "summarize_day_ahead": self.summarize_day_ahead,
            "decline_physical_layer": self.decline_physical_layer,
            "decline_out_of_scope": self.decline_out_of_scope,
        }
        if name not in dispatch:
            raise ValueError(f"Unknown analytical tool: {name}")
        return dispatch[name](arguments, memory)

    def get_traffic_forecast(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_value = self._resolve_time(args, memory)
        traffic = self._traffic_row(self._row_at(time_value))
        evidence = {
            "category": "traffic_forecast",
            "timestamp": time_value,
            "traffic": traffic,
            "provenance": self._xgb_model_evidence(),
        }
        fallback = (
            f"At {time_value}, predicted traffic is {traffic['total_gbps']:.2f} Gbps total: "
            f"Enterprise {traffic['enterprise_gbps']:.2f} Gbps, RAN {traffic['ran_gbps']:.2f} Gbps, and PON {traffic['pon_gbps']:.2f} Gbps."
        )
        return evidence, fallback

    def get_sla_prediction(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_value = self._resolve_time(args, memory)
        sla = self._sla_row(self._row_at(time_value))
        evidence = {
            "category": "sla_prediction",
            "timestamp": time_value,
            "sla": sla,
            "provenance": self._rf_model_evidence(),
        }
        fallback = (
            f"At {time_value}, the predicted SLA state is {sla['state'].replace('_', '-')} and the Failure-prone risk is "
            f"{100*sla['failure_prone_probability']:.1f}%."
        )
        evidence["rendered_values"] = {"failure_risk_percent": round(100 * sla["failure_prone_probability"], 1)}
        return evidence, fallback

    def get_network_state_at_time(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_value = self._resolve_time(args, memory)
        policy = self._policy_or_default(args.get("policy"), self.controller["active_policy"])
        row = self._row_at(time_value)
        compact = self._compact_policy_result(self.simulator.at_time(policy, time_value))
        evidence = {
            "category": "network_state",
            "timestamp": time_value,
            "network": self._network_evidence(),
            "traffic": self._traffic_row(row),
            "sla": self._sla_row(row),
            "provenance": {"traffic_forecast": self._xgb_model_evidence(), "sla_prediction": self._rf_model_evidence()},
            "simulated_active_policy": str(self.controller["active_policy"]).upper(),
            "displayed_policy": policy,
            "policy_state": compact,
            "scope_note": "Advisory representative-access-node policy replay; no physical actuation is performed.",
        }
        fallback = (
            f"At {time_value}, predicted traffic is {evidence['traffic']['total_gbps']:.2f} Gbps and the SLA state is "
            f"{evidence['sla']['state'].replace('_', '-')} with {100*evidence['sla']['failure_prone_probability']:.1f}% Failure-prone risk. "
            f"Under {policy}, the SC state is {compact['assignment_label']}, with {100*compact['overall_blocking_ratio_epoch']:.2f}% blocking "
            f"and {compact['reconfig_count']} SC reconfiguration(s)."
        )
        evidence["rendered_values"] = {
            "blocking_percent": round(100 * compact["overall_blocking_ratio_epoch"], 2),
            "failure_risk_percent": round(100 * evidence["sla"]["failure_prone_probability"], 1),
        }
        return evidence, fallback

    def explain_sla_risk(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_value = self._resolve_time(args, memory)
        row = self._row_at(time_value)
        claimed = args.get("claimed_state")
        sla = self._sla_row(row)
        premise_match = claimed is None or str(claimed) == sla["state"]
        evidence = {
            "category": "sla_risk_explanation",
            "timestamp": time_value,
            "traffic": self._traffic_row(row),
            "sla": sla,
            "claimed_state": claimed,
            "premise_matches_prediction": premise_match,
            "provenance": {"traffic_forecast": self._xgb_model_evidence(), "sla_prediction": self._rf_model_evidence()},
            "interpretation_boundary": "No causal feature attribution is available; concurrent traffic provides context only.",
            "causal_attribution_available": False,
        }
        risk_pct = round(100 * sla["failure_prone_probability"], 1)
        evidence["rendered_values"] = {"failure_risk_percent": risk_pct}
        if not premise_match:
            fallback = (
                f"The premise does not match the current prediction: at {time_value} the SLA state is {sla['state'].replace('_', '-')} "
                f"with {risk_pct:.1f}% Failure-prone risk, not {str(claimed).replace('_', '-')}. "
                "I can explain the predicted state, but this demonstrator does not provide causal feature attribution."
            )
        else:
            fallback = (
                f"At {time_value}, the predicted SLA state is {sla['state'].replace('_', '-')} with {risk_pct:.1f}% Failure-prone risk. "
                f"Concurrent predicted traffic is {evidence['traffic']['total_gbps']:.2f} Gbps. This contextualizes the prediction but is not a causal explanation."
            )
        return evidence, fallback

    def compare_policies_at_time(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_value = self._resolve_time(args, memory)
        objective = str(args.get("objective") or self.recommendation_cfg["default_objective"])
        results = {p: self._compact_policy_result(self.simulator.at_time(p, time_value)) for p in POLICIES}
        recommended = self._recommend_policy(results, objective)
        evidence = {
            "category": "policy_comparison",
            "timestamp": time_value,
            "objective": objective,
            "policy_results": results,
            "recommended_policy": recommended,
            "operator_policy_version": str(self.operator_policy["version"]),
            "recommendation_is_advisory": True,
        }
        r = results[recommended]
        fallback = (
            f"At {time_value}, the {objective.replace('_', ' ')} objective recommends {recommended}. "
            f"Its simulated blocking is {100*r['overall_blocking_ratio_epoch']:.2f}% with {r['reconfig_count']} SC reconfiguration(s). "
            "The recommendation is advisory; PCA, MBA, and SAA remain available for comparison."
        )
        evidence["rendered_values"] = {p: {"blocking_percent": round(100 * v["overall_blocking_ratio_epoch"], 2)} for p, v in results.items()}
        return evidence, fallback

    def simulate_policy_at_time(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_value = self._resolve_time(args, memory)
        policy = self._policy_or_default(args.get("policy"), memory.get("recommended_policy") or self.controller["active_policy"])
        result = self._compact_policy_result(self.simulator.at_time(policy, time_value))
        evidence = {
            "category": "policy_counterfactual",
            "timestamp": time_value,
            "policy": policy,
            "simulated_result": result,
            "counterfactual": True,
            "advisory": True,
        }
        fallback = (
            f"At {time_value}, {policy} produces {result['assignment_label']}, with {100*result['overall_blocking_ratio_epoch']:.2f}% overall blocking, "
            f"{100*result['fresh_service_ratio']:.2f}% fresh-service ratio, and {result['reconfig_count']} SC reconfiguration(s)."
        )
        evidence["rendered_values"] = {
            "blocking_percent": round(100 * result["overall_blocking_ratio_epoch"], 2),
            "fresh_service_percent": round(100 * result["fresh_service_ratio"], 2),
        }
        return evidence, fallback

    def analyze_constrained_allocation(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_value = self._resolve_time(args, memory)
        fixed: dict[str, int] = {}
        mapping = {"enterprise_subcarriers": "enterprise", "ran_subcarriers": "ran", "pon_subcarriers": "pon"}
        for key, service in mapping.items():
            if key in args and args[key] is not None:
                fixed[service] = int(args[key])
        if not fixed:
            raise ValueError("At least one SC-count constraint is required.")
        objective = str(args.get("objective") or self.recommendation_cfg["default_objective"])
        reference_policy = self._policy_or_default(args.get("reference_policy"), memory.get("recommended_policy") or self.controller["active_policy"])
        tolerance = float(self.recommendation_cfg["objectives"]["balanced"].get("blocking_tolerance_ratio", 0.005))
        result = self.simulator.constrained(time_value, fixed, reference_policy, objective, tolerance)
        evidence = {"category": "operator_constraint", "timestamp": time_value, **result}
        if not result["constraint_feasible"]:
            return evidence, f"The SC constraint at {time_value} is infeasible: {result['reason']}"
        r = self._compact_policy_result(result["result"])
        evidence["result"] = r
        evidence["rendered_values"] = {"blocking_percent": round(100 * r["overall_blocking_ratio_epoch"], 2)}
        fallback = (
            f"At {time_value}, the constraint is feasible. The preferred SC state is {r['assignment_label']} under the {objective.replace('_', ' ')} objective, "
            f"with {100*r['overall_blocking_ratio_epoch']:.2f}% blocking and {r['reconfig_count']} SC reconfiguration(s)."
        )
        return evidence, fallback

    def compare_network_states(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_a, time_b = self._resolve_pair(args, memory)
        policy = self._policy_or_default(args.get("policy"), memory.get("recommended_policy") or self.controller["active_policy"])
        a, b = self._row_at(time_a), self._row_at(time_b)
        pa = self._compact_policy_result(self.simulator.at_time(policy, time_a))
        pb = self._compact_policy_result(self.simulator.at_time(policy, time_b))
        deltas = {
            "total_gbps": round(float(b["total_gbps"] - a["total_gbps"]), 4),
            "enterprise_gbps": round(float(b["enterprise_gbps"] - a["enterprise_gbps"]), 4),
            "ran_gbps": round(float(b["ran_gbps"] - a["ran_gbps"]), 4),
            "pon_gbps": round(float(b["pon_gbps"] - a["pon_gbps"]), 4),
            "failure_prone_probability": round(float(b["failure_probability"] - a["failure_probability"]), 6),
            "blocking_ratio": round(float(pb["overall_blocking_ratio_epoch"] - pa["overall_blocking_ratio_epoch"]), 8),
            "reconfig_count": int(pb["reconfig_count"] - pa["reconfig_count"]),
        }
        evidence = {
            "category": "cross_time_comparison",
            "time_a": time_a,
            "time_b": time_b,
            "policy": policy,
            "state_a": {"traffic": self._traffic_row(a), "sla": self._sla_row(a), "policy": pa},
            "state_b": {"traffic": self._traffic_row(b), "sla": self._sla_row(b), "policy": pb},
            "delta_b_minus_a": deltas,
        }
        fallback = (
            f"From {time_a} to {time_b}, predicted total traffic changes by {deltas['total_gbps']:+.2f} Gbps and Failure-prone risk by "
            f"{100*deltas['failure_prone_probability']:+.1f} percentage points. Under {policy}, blocking changes by {100*deltas['blocking_ratio']:+.2f} percentage points."
        )
        evidence["rendered_values"] = {
            "blocking_delta_percentage_points": round(100 * deltas["blocking_ratio"], 2),
            "failure_risk_delta_percentage_points": round(100 * deltas["failure_prone_probability"], 1),
        }
        return evidence, fallback

    def find_risk_intervals(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        metric = str(args.get("metric") or "failure_probability")
        top_k = max(1, min(10, int(args.get("top_k") or 3)))
        trace = None
        if metric == "blocking":
            policy = str(memory.get("recommended_policy") or self.controller["active_policy"]).upper()
            trace = self.simulator.replay(policy)
            values = pd.Series([x["overall_blocking_ratio_epoch"] for x in trace])
        elif metric == "reconfiguration":
            policy = str(memory.get("recommended_policy") or self.controller["active_policy"]).upper()
            trace = self.simulator.replay(policy)
            values = pd.Series([x["reconfig_count"] for x in trace])
        elif metric == "total_gbps":
            policy = None
            values = self.frame["total_gbps"]
        else:
            metric, policy = "failure_probability", None
            values = self.frame["failure_probability"]
        indices = values.nlargest(top_k).index.tolist()
        intervals = []
        for idx in indices:
            row = self.frame.iloc[int(idx)]
            item = {
                "time": str(row["time"]),
                "total_gbps": round(float(row["total_gbps"]), 2),
                "sla_state": str(row["predicted_state"]),
                "failure_prone_probability": round(float(row["failure_probability"]), 4),
            }
            if policy and trace is not None:
                pr = trace[int(idx)]
                item.update({"policy": policy, "blocking_ratio": pr["overall_blocking_ratio_epoch"], "reconfig_count": pr["reconfig_count"]})
            intervals.append(item)
        evidence = {"category": "risk_intervals", "metric": metric, "top_k": top_k, "intervals": intervals}
        if policy:
            evidence["policy"] = policy
        fallback = f"The highest-ranked interval by {metric.replace('_', ' ')} is {intervals[0]['time']}; {top_k} interval(s) are returned for comparison."
        return evidence, fallback

    def summarize_time_range(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        start = str(args.get("start_time") or "00:00")
        end = str(args.get("end_time") or "23:55")
        start_m, end_m = self.simulator._parse_time(start), self.simulator._parse_time(end)
        if end_m < start_m:
            raise ValueError("end_time must not be earlier than start_time for this day-ahead summary.")
        subset = self.frame[(self.frame.minute_of_day >= start_m) & (self.frame.minute_of_day <= end_m)].copy()
        if subset.empty:
            raise ValueError("No intervals are available in the requested range.")

        peak_load = subset.loc[subset["total_gbps"].idxmax()]
        peak_risk = subset.loc[subset["failure_probability"].idxmax()]
        state_counts = subset["predicted_state"].value_counts()
        policy_summaries: dict[str, Any] = {}
        recommendation_counts: Counter[str] = Counter()
        for policy in POLICIES:
            trace = [x for x in self.simulator.replay(policy) if start_m <= x["minute_of_day"] <= end_m]
            policy_summaries[policy] = {
                "mean_blocking_ratio": round(sum(x["overall_blocking_ratio_epoch"] for x in trace) / len(trace), 8),
                "max_blocking_ratio": round(max(x["overall_blocking_ratio_epoch"] for x in trace), 8),
                "total_reconfigurations": int(sum(x["reconfig_count"] for x in trace)),
            }
        objective = str(args.get("objective") or self.recommendation_cfg["default_objective"])
        for _, row in subset.iterrows():
            t = str(row["time"])
            results = {p: self._compact_policy_result(self.simulator.at_time(p, t)) for p in POLICIES}
            recommendation_counts[self._recommend_policy(results, objective)] += 1

        summary = {
            "interval_count": int(len(subset)),
            "mean_total_gbps": round(float(subset.total_gbps.mean()), 4),
            "peak_total_gbps": round(float(peak_load["total_gbps"]), 4),
            "peak_load_time": str(peak_load["time"]),
            "mean_failure_prone_probability": round(float(subset.failure_probability.mean()), 6),
            "max_failure_prone_probability": round(float(peak_risk["failure_probability"]), 6),
            "highest_risk_time": str(peak_risk["time"]),
            "state_counts": {s: int(state_counts.get(s, 0)) for s in ("normal", "degraded", "failure_prone")},
            "policy_summaries": policy_summaries,
            "recommendation_counts": {p: int(recommendation_counts.get(p, 0)) for p in POLICIES},
            "objective": objective,
        }
        evidence = {"category": "time_range_summary", "start_time": start, "end_time": end, "summary": summary}
        dominant = max(POLICIES, key=lambda p: recommendation_counts.get(p, 0))
        fallback = (
            f"From {start} to {end}, {len(subset)} five-minute intervals were analysed. Mean load is {summary['mean_total_gbps']:.2f} Gbps; "
            f"peak load is {summary['peak_total_gbps']:.2f} Gbps at {summary['peak_load_time']}. The highest Failure-prone risk occurs at {summary['highest_risk_time']}. "
            f"Under the {objective.replace('_', ' ')} objective, {dominant} is recommended most often in this range."
        )
        return evidence, fallback

    def explain_recommendation_change(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_a, time_b = self._resolve_pair(args, memory)
        objective = str(args.get("objective") or self.recommendation_cfg["default_objective"])
        ra = {p: self._compact_policy_result(self.simulator.at_time(p, time_a)) for p in POLICIES}
        rb = {p: self._compact_policy_result(self.simulator.at_time(p, time_b)) for p in POLICIES}
        rec_a, rec_b = self._recommend_policy(ra, objective), self._recommend_policy(rb, objective)
        evidence = {
            "category": "recommendation_change",
            "time_a": time_a,
            "time_b": time_b,
            "objective": objective,
            "recommended_at_a": rec_a,
            "recommended_at_b": rec_b,
            "policy_results_a": ra,
            "policy_results_b": rb,
            "changed": rec_a != rec_b,
            "explanation_basis": "Only deterministic blocking/reconfiguration metrics and configured tie-break rules are used.",
        }
        if rec_a == rec_b:
            fallback = f"The recommendation does not change: {rec_a} is preferred at both {time_a} and {time_b} for the {objective.replace('_', ' ')} objective."
        else:
            fallback = f"The recommendation changes from {rec_a} at {time_a} to {rec_b} at {time_b} because the deterministic blocking/reconfiguration trade-off differs between the intervals."
        return evidence, fallback

    def summarize_policy_history(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        objective = str(args.get("objective") or self.recommendation_cfg["default_objective"])
        timeline = []
        for _, row in self.frame.iterrows():
            t = str(row["time"])
            results = {p: self._compact_policy_result(self.simulator.at_time(p, t)) for p in POLICIES}
            timeline.append((t, self._recommend_policy(results, objective)))
        counts = Counter(policy for _, policy in timeline)
        changes, previous = [], None
        for time_value, policy in timeline:
            if previous != policy:
                changes.append({"time": time_value, "recommended_policy": policy})
                previous = policy
        evidence = {
            "category": "policy_history",
            "objective": objective,
            "recommendation_counts": {p: int(counts.get(p, 0)) for p in POLICIES},
            "change_points": changes,
            "change_count": max(0, len(changes) - 1),
        }
        dominant = max(POLICIES, key=lambda p: counts.get(p, 0))
        fallback = f"Across the day, {dominant} is recommended most often under the {objective.replace('_', ' ')} objective, with {evidence['change_count']} recommendation change(s)."
        return evidence, fallback

    def get_evidence_confidence(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_value = self._resolve_time(args, memory)
        policy = str(args.get("policy") or memory.get("recommended_policy") or self.controller["active_policy"]).upper()
        layers = {
            "traffic_forecast": True,
            "sla_prediction": True,
            "deterministic_policy_replay": True,
            "grounding_guardrail": True,
            "physical_layer_telemetry": False,
        }
        evidence = {
            "category": "evidence_confidence",
            "timestamp": time_value,
            "policy": policy,
            "evidence_layers": layers,
            "available_evidence_layers": sum(int(v) for v in layers.values()),
            "total_evidence_layers_listed": len(layers),
            "important_limitations": [
                self.model_cfg["sla_classifier"]["limitation"],
                "Physical-layer telemetry is unavailable.",
                "This is advisory simulation, not closed-loop actuation.",
            ],
            "meaning": "Evidence coverage is not a calibrated probability that the recommendation is correct and is not LLM self-confidence.",
        }
        fallback = (
            f"For the analysis at {time_value}, {evidence['available_evidence_layers']} of {evidence['total_evidence_layers_listed']} listed evidence layers are available. "
            "This is evidence coverage, not a confidence probability; physical-layer telemetry is unavailable."
        )
        return evidence, fallback

    def validate_recommendation(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_value = self._resolve_time(args, memory)
        target = str(args.get("target") or "last_result")
        if target == "last_result" and memory.get("last_tool") == "analyze_constrained_allocation" and memory.get("last_constraints"):
            fixed = dict(memory["last_constraints"])
            reference_policy = str(memory.get("last_reference_policy") or self.controller["active_policy"]).upper()
            objective = str(memory.get("last_objective") or self.recommendation_cfg["default_objective"])
            tolerance = float(self.recommendation_cfg["objectives"]["balanced"].get("blocking_tolerance_ratio", 0.005))
            first = self.simulator.constrained(time_value, fixed, reference_policy, objective, tolerance)
            second = PolicySimulator(self.frame, PolicyRegistry.load()).constrained(time_value, fixed, reference_policy, objective, tolerance)
            checks = {"constraint_feasible": bool(first.get("constraint_feasible")), "independent_recompute_match": self._json_equal(first, second)}
            if first.get("constraint_feasible"):
                checks.update(self._policy_checks(first["result"], fixed))
            evidence = {
                "category": "validation",
                "timestamp": time_value,
                "validation_target": "operator_constrained_allocation",
                "operator_constraints": fixed,
                "reference_policy": reference_policy,
                "objective": objective,
                "deterministic_checks": checks,
                "all_policy_checks_passed": all(checks.values()),
                "forecast_validation_summary": self._ml_validation_summary(),
                "trust_boundary": self._trust_boundary(),
            }
            fallback = f"Validation of the constrained allocation at {time_value} {'passed' if all(checks.values()) else 'did not fully pass'}; constraints and independent recomputation were checked."
            return evidence, fallback

        policy = str(args.get("policy") or memory.get("recommended_policy") or memory.get("last_policy") or self.controller["active_policy"]).upper()
        first = self.simulator.at_time(policy, time_value)
        fresh = PolicySimulator(self.frame, PolicyRegistry.load()).at_time(policy, time_value)
        checks = self._policy_checks(first)
        checks["independent_recompute_match"] = self._comparable_policy_result(first) == self._comparable_policy_result(fresh)
        evidence = {
            "category": "validation",
            "timestamp": time_value,
            "validation_target": "policy_result",
            "policy": policy,
            "policy_result": self._compact_policy_result(first),
            "deterministic_checks": checks,
            "all_policy_checks_passed": all(checks.values()),
            "forecast_validation_summary": self._ml_validation_summary(),
            "trust_boundary": self._trust_boundary(),
            "backlog_metric_note": "Backlog metrics are not fabricated because the counterfactual PSC replay has no carry-over backlog model.",
        }
        fallback = f"Validation for {policy} at {time_value} {'passed' if all(checks.values()) else 'did not fully pass'}; SC budget, traffic conservation, KPI bounds, and independent recomputation were checked."
        return evidence, fallback

    def analyze_network(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        time_value = self._resolve_time(args, memory)
        objective = str(args.get("objective") or self.recommendation_cfg["default_objective"])
        traffic, _ = self.get_traffic_forecast({"time": time_value}, memory)
        sla, _ = self.get_sla_prediction({"time": time_value}, memory)
        policies, _ = self.compare_policies_at_time({"time": time_value, "objective": objective}, memory)
        coverage, _ = self.get_evidence_confidence({"time": time_value, "policy": policies["recommended_policy"]}, memory)
        evidence = {
            "category": "structured_analysis",
            "timestamp": time_value,
            "objective": objective,
            "traffic_analysis": traffic,
            "sla_analysis": sla,
            "policy_analysis": policies,
            "evidence_summary": coverage,
            "recommended_policy": policies["recommended_policy"],
        }
        r = policies["policy_results"][policies["recommended_policy"]]
        fallback = (
            f"At {time_value}, predicted traffic, SLA risk, and deterministic PCA/MBA/SAA replay were analysed together. "
            f"Under the {objective.replace('_', ' ')} objective, {policies['recommended_policy']} is recommended with {100*r['overall_blocking_ratio_epoch']:.2f}% simulated blocking."
        )
        return evidence, fallback

    def summarize_day_ahead(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        counts = self.frame["predicted_state"].value_counts()
        peak = self.frame.loc[self.frame["failure_probability"].idxmax()]
        evidence = {
            "category": "day_summary",
            "intervals": int(len(self.frame)),
            "state_counts": {s: int(counts.get(s, 0)) for s in ("normal", "degraded", "failure_prone")},
            "highest_risk": {"traffic": self._traffic_row(peak), "sla": self._sla_row(peak)},
            "active_simulated_policy": str(self.controller["active_policy"]).upper(),
            "provenance": {"traffic_forecast": self._xgb_model_evidence(), "sla_prediction": self._rf_model_evidence()},
        }
        fallback = f"The day-ahead analysis contains {len(self.frame)} five-minute intervals. The highest Failure-prone risk occurs at {peak['time']} with {peak['total_gbps']:.2f} Gbps predicted traffic."
        return evidence, fallback

    def decline_physical_layer(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        evidence = {
            "category": "physical_layer_out_of_scope",
            "unsupported": ["GNPy", "OSNR", "BER", "Q-factor", "fiber-cut diagnosis", "physical-layer fault localization"],
            "reason": "No physical-layer telemetry or calibrated physical-layer model is available in this demonstrator.",
        }
        return evidence, "Physical-layer diagnosis is outside this v1 demonstrator because calibrated physical-layer parameters are not yet available. I can analyze predicted traffic, SLA risk, PCA/MBA/SAA behavior, temporal changes, and SC constraints."

    def decline_out_of_scope(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[dict[str, Any], str]:
        evidence = {
            "category": "generic_out_of_scope",
            "supported": ["traffic forecast", "SLA state", "timestamp comparison", "PCA/MBA/SAA policy analysis", "SC constraints", "time-range analysis"],
        }
        return evidence, "That request is outside the network-operations scope of this demonstrator. I can help with traffic forecasts, SLA-risk analysis, timestamp comparisons, SC-allocation policies, operator constraints, and time-range analysis."

    def _recommend_policy(self, results: dict[str, dict[str, Any]], objective: str) -> str:
        if objective not in self.recommendation_cfg["tie_break_order"]:
            objective = self.recommendation_cfg["default_objective"]
        tie_order = self.recommendation_cfg["tie_break_order"][objective]
        order = {policy: i for i, policy in enumerate(tie_order)}
        if objective == "sla_priority":
            return "PCA"
        if objective == "min_reconfiguration":
            return min(results, key=lambda p: (results[p]["reconfig_count"], results[p]["overall_blocking_ratio_epoch"], order[p]))
        if objective == "min_blocking":
            return min(results, key=lambda p: (results[p]["overall_blocking_ratio_epoch"], results[p]["reconfig_count"], order[p]))
        tolerance = float(self.recommendation_cfg["objectives"]["balanced"].get("blocking_tolerance_ratio", 0.005))
        min_block = min(v["overall_blocking_ratio_epoch"] for v in results.values())
        near = [p for p, v in results.items() if v["overall_blocking_ratio_epoch"] <= min_block + tolerance + 1e-12]
        return min(near, key=lambda p: (results[p]["reconfig_count"], results[p]["weighted_reconfig_cost"], order[p]))

    def _resolve_time(self, args: dict[str, Any], memory: dict[str, Any]) -> str:
        candidate = args.get("time") or memory.get("last_time")
        if candidate:
            minute = self.simulator._parse_time(str(candidate))
            if minute not in set(self.frame.minute_of_day.astype(int)):
                raise ValueError(f"Timestamp {candidate} is not available in the forecast grid.")
            return f"{minute//60:02d}:{minute%60:02d}"
        row = self.frame.loc[self.frame["failure_probability"].idxmax()]
        return str(row["time"])

    def _resolve_pair(self, args: dict[str, Any], memory: dict[str, Any]) -> tuple[str, str]:
        a, b = args.get("time_a"), args.get("time_b")
        if not a and memory.get("comparison_time_a"):
            a = memory["comparison_time_a"]
        if not b and memory.get("last_time"):
            b = memory["last_time"]
        if not a or not b:
            raise ValueError("Two timestamps are required for this comparison.")
        return self._resolve_time({"time": a}, {}), self._resolve_time({"time": b}, {})

    def _row_at(self, time_value: str) -> pd.Series:
        minute = self.simulator._parse_time(time_value)
        row = self.frame.loc[self.frame["minute_of_day"] == minute]
        if row.empty:
            raise ValueError(f"Timestamp {time_value} is not available.")
        return row.iloc[0]

    @staticmethod
    def _traffic_row(row: pd.Series) -> dict[str, Any]:
        return {
            "time": str(row["time"]),
            "enterprise_gbps": round(float(row["enterprise_gbps"]), 2),
            "ran_gbps": round(float(row["ran_gbps"]), 2),
            "pon_gbps": round(float(row["pon_gbps"]), 2),
            "total_gbps": round(float(row["total_gbps"]), 2),
        }

    @staticmethod
    def _sla_row(row: pd.Series) -> dict[str, Any]:
        return {
            "time": str(row["time"]),
            "state": str(row["predicted_state"]),
            "failure_prone_probability": round(float(row["prob_failure_prone"]), 4),
            "internal_probabilities": {
                "normal": round(float(row["prob_normal"]), 4),
                "degraded": round(float(row["prob_degraded"]), 4),
                "failure_prone": round(float(row["prob_failure_prone"]), 4),
            },
        }

    def _xgb_model_evidence(self) -> dict[str, Any]:
        return {
            "model": self.model_cfg["forecast"]["name"],
            "version": self.model_cfg["forecast"]["version"],
            "execution_mode": self.forecast_mode,
            "saved_model_inference": self.forecast_mode == "live",
            "source_of_truth": True,
        }

    def _rf_model_evidence(self) -> dict[str, Any]:
        metadata = {}
        if config.CLASSIFIER_METADATA.exists():
            metadata = json.loads(config.CLASSIFIER_METADATA.read_text(encoding="utf-8"))
        return {
            "model": self.model_cfg["sla_classifier"]["name"],
            "version": self.model_cfg["sla_classifier"]["version"],
            "saved_model_inference": True,
            "source_of_truth": True,
            "risk_score_definition": "Probability assigned to the simulator-derived failure_prone state.",
            "label_basis": "Training labels are derived from simulator blocking ratio: zero=normal, positive up to the learned threshold=degraded, above threshold=failure_prone.",
            "failure_blocking_threshold": metadata.get("failure_threshold"),
            "limitation": self.model_cfg["sla_classifier"]["limitation"],
        }

    def _network_evidence(self) -> dict[str, Any]:
        return {
            "topology_type": self.network["topology_type"],
            "hub_capacity_gbps": float(self.network["hub_capacity_gbps"]),
            "hub_subcarriers": int(self.network["hub_subcarriers"]),
            "access_nodes": int(self.network["access_nodes"]),
            "leaf_capacity_gbps": float(self.network["leaf_capacity_gbps"]),
            "subcarriers_per_leaf": int(self.network["subcarriers_per_leaf"]),
            "subcarrier_capacity_gbps": float(self.network["subcarrier_capacity_gbps"]),
            "representative_leaf": str(self.controller.get("representative_leaf", "A1")),
        }

    @staticmethod
    def _compact_policy_result(value: dict[str, Any]) -> dict[str, Any]:
        keys = [
            "policy", "assignment", "assignment_label", "allocation_counts", "active_subcarriers", "idle_subcarriers",
            "demand_gbps", "capacity_gbps", "served_new_gbps", "blocked_new_gbps", "overall_blocking_ratio_epoch",
            "blocking_event", "per_class_blocking_ratio", "fresh_service_ratio", "reconfig_event", "reconfig_count",
            "weighted_reconfig_cost", "backlog_pressure_ratio", "backlog_recovery_ratio",
        ]
        return {k: value.get(k) for k in keys}

    @staticmethod
    def _comparable_policy_result(value: dict[str, Any]) -> dict[str, Any]:
        keys = ["assignment", "capacity_gbps", "served_new_gbps", "blocked_new_gbps", "overall_blocking_ratio_epoch", "fresh_service_ratio", "reconfig_count"]
        return {k: value.get(k) for k in keys}

    def _policy_checks(self, value: dict[str, Any], fixed: dict[str, int] | None = None) -> dict[str, bool]:
        checks = {
            "four_subcarrier_states": len(value["assignment"]) == int(self.network["subcarriers_per_leaf"]),
            "known_assignment_states": all(x in ASSIGNMENT_STATES for x in value["assignment"]),
            "traffic_conservation": all(abs(value["served_new_gbps"][s] + value["blocked_new_gbps"][s] - value["demand_gbps"][s]) < 1e-6 for s in SERVICES),
            "blocking_ratio_bounded": 0.0 <= value["overall_blocking_ratio_epoch"] <= 1.0,
            "fresh_service_ratio_bounded": 0.0 <= value["fresh_service_ratio"] <= 1.0,
        }
        if fixed:
            checks["operator_constraints_preserved"] = all(value["assignment"].count(s) == int(c) for s, c in fixed.items())
        return checks

    @staticmethod
    def _json_equal(a: Any, b: Any) -> bool:
        return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)

    def _trust_boundary(self) -> dict[str, Any]:
        return {
            "mistral_calculates_network_values": False,
            "ml_models_provide_predictions": True,
            "policy_engine_is_deterministic": True,
            "llm_answer_is_numeric_grounding_checked": True,
            "false_premises_are_checked_against_tool_evidence": True,
            "physical_layer_diagnosis_supported": False,
        }

    def _ml_validation_summary(self) -> dict[str, Any]:
        path = config.VALIDATION_DIR / "results" / "ml_validation_summary.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        metrics = pd.read_csv(config.REGRESSION_METRICS)
        avg = metrics[(metrics["model"] == "xgboost") & (metrics["target"] == "average")]
        if avg.empty:
            return {"available": False}
        row = avg.iloc[0]
        return {
            "available": True,
            "xgboost_average_mae_gbps": float(row["mae"]),
            "xgboost_average_rmse_gbps": float(row["rmse"]),
            "xgboost_average_r2": float(row["r2"]),
        }
