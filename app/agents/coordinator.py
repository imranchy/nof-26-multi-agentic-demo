from __future__ import annotations

import json
import re
from typing import Any
from urllib.request import Request, urlopen

from app import config
from app.semantic import SemanticResolver

POLICY = {"type": "string", "enum": ["PCA", "MBA", "SAA"]}
TIME = {"type": "string", "description": "24-hour HH:MM timestamp on the available 5-minute grid"}
OBJECTIVE = {"type": "string", "enum": ["balanced", "min_blocking", "min_reconfiguration", "sla_priority"]}
SC_COUNT = {"type": "integer", "minimum": 0, "maximum": 4}
METRIC = {"type": "string", "enum": ["failure_probability", "total_gbps", "blocking", "reconfiguration"]}


def _tool(name: str, description: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties or {}},
    }


# Keep the LLM-visible API deliberately small and semantically distinct. Internal
# validation/provenance functions exist elsewhere but are not exposed as operator
# intents in v1.
TOOLS = [
    _tool("get_traffic_forecast", 
          "Return predicted Enterprise, RAN, PON, and total offered traffic at one timestamp.", 
          {"time": TIME}),
    _tool("get_sla_prediction", "Return predicted SLA state and Failure-prone risk at one timestamp.", {"time": TIME}),
    _tool("explain_sla_risk", "Explain/correct a predicted SLA state using validated risk evidence and concurrent traffic as non-causal context.", {"time": TIME}),
    _tool("get_network_state_at_time", 
           "Retrieve the network-state snapshot at a timestamp. "
            "Use for requests asking for the network state, status, snapshot, "
            "current condition, traffic/SLA/SC state, or state under a named policy. "
            "Do NOT use when the operator asks what a policy would do, its "
            "performance, outcome, counterfactual behavior, hypothetical result, "
            "or asks to simulate/try a policy. "
            "Those requests must use simulate_policy_at_time.", 
          {"time": TIME, "policy": POLICY}),
    _tool("compare_policies_at_time", "Compare PCA, MBA, and SAA at one timestamp and recommend according to an operator objective.", {"time": TIME, "objective": OBJECTIVE}),
    _tool("simulate_policy_at_time", 
           "Simulate the deterministic counterfactual outcome of one named "
        "allocation policy (PCA, MBA, or SAA) at a timestamp. "
        "Use when the operator asks what a policy would do, what happens "
        "if it is used, its performance, its outcome, a counterfactual, "
        "a hypothetical result, or asks to simulate or try a policy instead. "
        "Strong trigger phrases include: 'what if', 'what would', "
        "'performance', 'outcome', 'simulate', 'counterfactual', "
        "'try instead', and 'if we use'. "
        "Do NOT use for ordinary network-state snapshots.",
          {"time": TIME, 
           "policy": POLICY}),
    _tool("analyze_constrained_allocation", "Evaluate explicit operator SC-count constraints and choose the best feasible four-SC assignment.", {
        "time": TIME,
        "enterprise_subcarriers": SC_COUNT,
        "ran_subcarriers": SC_COUNT,
        "pon_subcarriers": SC_COUNT,
        "reference_policy": POLICY,
        "objective": OBJECTIVE,
    }),
    _tool("compare_network_states", "Compare network state, traffic, SLA risk, and policy KPIs at two timestamps.", {"time_a": TIME, "time_b": TIME, "policy": POLICY}),
    _tool("find_risk_intervals", "Find top-k highest-risk, highest-load, highest-blocking, or highest-reconfiguration intervals.", {"metric": METRIC, "top_k": {"type": "integer", "minimum": 1, "maximum": 10}}),
    _tool("summarize_time_range", "Summarize traffic, SLA state distribution, policy blocking, reconfiguration, and recommendations over a time range.", {"start_time": TIME, "end_time": TIME, "objective": OBJECTIVE}),
    _tool("decline_physical_layer", "Use only for physical-layer requests such as OSNR, BER, Q-factor, fiber-cut, or GNPy analysis."),
    _tool("decline_out_of_scope", "Use for generic non-network requests."),
]

TOOL_NAMES = {tool["name"] for tool in TOOLS}


class CoordinatorAgent:
    """Mistral performs semantic routing and bounded tool planning only."""

    def __init__(self, use_llm: bool = True) -> None:
        self.use_llm = use_llm
        self.history: list[dict[str, Any]] = []
        self.last_audit: dict[str, Any] = {}

    def select_plan(self, query: str, memory: dict[str, Any] | None = None) -> list[tuple[str, dict[str, Any]]]:
        if not self.use_llm:
            raise RuntimeError("LLM tool selection is disabled.")
        memory = memory or {}
        include_history = bool(memory)
        prompt = f"""{config.coordinator_prompt()}

Available tools and JSON argument schemas:
{json.dumps(TOOLS, ensure_ascii=False)}

Recent conversation context:
{self._history_text(include_history)}

Deterministic conversation memory:
{json.dumps(memory, ensure_ascii=False)}

Current operator request:
{query}

Return ONLY JSON in this exact shape:
{{"steps":[{{"name":"tool_name","arguments":{{}}}}]}}
"""
        step_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "enum": sorted(TOOL_NAMES)},
                "arguments": {"type": "object"},
            },
            "required": ["name", "arguments"],
        }
        output_format = {
            "type": "object",
            "properties": {"steps": {"type": "array", "items": step_schema, "minItems": 1, "maxItems": 3}},
            "required": ["steps"],
        }

        attempts: list[dict[str, Any]] = []
        for attempt_no in (1, 2):
            payload = {
                "model": config.OLLAMA_MODEL,
                "prompt": prompt if attempt_no == 1 else prompt + "\nPrevious output was invalid. Emit compact valid JSON only; no markdown or commentary.",
                "stream": False,
                "format": output_format,
                "options": {"temperature": 0, "num_predict": 320},
            }
            try:
                request = Request(
                    f"{config.OLLAMA_URL}/api/generate",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(request, timeout=90) as response:
                    body = json.loads(response.read())
                raw_text = str(body.get("response", "")).strip()
                selected = self._parse_json(raw_text)
                result = self._validate_plan(selected)
                self.last_audit = {
                    "prompt_version": config.prompt_version("coordinator"),
                    "attempts": attempts + [{"attempt": attempt_no, "ok": True, "raw": raw_text}],
                    "parse_failed": False,
                    "fallback_used": False,
                }
                return result
            except Exception as exc:  # record retry rather than exposing brittle JSON failures to the UI
                attempts.append({"attempt": attempt_no, "ok": False, "error": f"{type(exc).__name__}: {exc}"})

        fallback = SemanticResolver.fallback_plan(query, memory)
        if fallback:
            self.last_audit = {
                "prompt_version": config.prompt_version("coordinator"),
                "attempts": attempts,
                "parse_failed": True,
                "fallback_used": True,
                "fallback_plan": [{"tool": n, "arguments": a} for n, a in fallback],
            }
            return fallback
        self.last_audit = {
            "prompt_version": config.prompt_version("coordinator"),
            "attempts": attempts,
            "parse_failed": True,
            "fallback_used": False,
        }
        raise RuntimeError(
            "Mistral tool planning failed after two structured-output attempts and no safe deterministic fallback matched the request. "
            "Confirm that Ollama is running and mistral:7b is installed."
        )

    @staticmethod
    def _parse_json(raw_text: str) -> dict[str, Any]:
        if not raw_text:
            raise ValueError("empty model response")
        try:
            value = json.loads(raw_text)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        # Conservative repair for occasional leading/trailing commentary.
        match = re.search(r"\{.*\}", raw_text, re.S)
        if not match:
            raise ValueError("no JSON object found")
        value = json.loads(match.group(0))
        if not isinstance(value, dict):
            raise ValueError("JSON response must be an object")
        return value

    @staticmethod
    def _validate_plan(selected: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        steps = selected.get("steps", [])
        if not isinstance(steps, list) or not 1 <= len(steps) <= 3:
            raise ValueError("Mistral must return between one and three tool steps")
        result: list[tuple[str, dict[str, Any]]] = []
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError("Each tool step must be an object")
            name = str(step.get("name", ""))
            args = step.get("arguments", {})
            if name not in TOOL_NAMES:
                raise ValueError(f"Unknown selected tool: {name}")
            if not isinstance(args, dict):
                raise ValueError("Tool arguments must be JSON objects")
            result.append((name, args))
        return result

    def select_tool(self, query: str, memory: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
        return self.select_plan(query, memory)[0]

    def record_turn(self, query: str, steps: list[dict[str, Any]], evidence: dict[str, Any], answer: str) -> None:
        self.history.append({
            "query": query,
            "steps": steps,
            "evidence_summary": self._compact_evidence(evidence),
            "answer": answer,
        })
        self.history = self.history[-8:]

    def reset(self) -> None:
        self.history.clear()
        self.last_audit = {}

    def _history_text(self, include_history: bool = True) -> str:
        if not include_history or not self.history:
            return "(none)"

        compact_history = []
        for item in self.history:
            compact_history.append({
                "query": item.get("query"),
                "steps": item.get("steps"),
                "evidence_summary": item.get("evidence_summary"),
            })

        return "\n".join(
            json.dumps(item, ensure_ascii=False)
            for item in compact_history
        )

    @staticmethod
    def _compact_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        keep = {"category", "timestamp", "time_a", "time_b", "recommended_policy", "policy", "objective"}
        result = {k: v for k, v in evidence.items() if k in keep}
        if "final" in evidence and isinstance(evidence["final"], dict):
            result["final"] = {k: evidence["final"].get(k) for k in keep if k in evidence["final"]}
        return result
