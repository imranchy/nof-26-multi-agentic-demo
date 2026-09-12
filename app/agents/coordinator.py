from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from app import config
from app.schemas import ContextInterpretation, CoordinatorDecision

CONTEXT_FIELDS = ["intent", "time", "policy", "objective", "constraints"]


class CoordinatorAgent:
    """Local Mistral conversational-context interpreter.

    This stage decides only how the current utterance relates to validated
    structured state. Native function calling in the next stage chooses the
    analytical capability. Python never performs natural-language routing.
    """

    def __init__(self, use_llm: bool = True) -> None:
        self.use_llm = use_llm
        self.history: list[dict[str, Any]] = []
        self.last_audit: dict[str, Any] = {}

    def select_decision(self, query: str, memory: dict[str, Any] | None = None) -> CoordinatorDecision:
        if not self.use_llm:
            raise RuntimeError("LLM context interpretation is disabled.")

        memory = memory or {}
        prompt = f"""{config.coordinator_prompt()}

You are the conversational-context stage of a fully local optical-network assistant.
Do not choose a network tool here. A separate native Mistral function-calling stage selects the tool.

Structured conversation memory from previous deterministic execution:
{json.dumps(self._compact_memory(memory), ensure_ascii=False)}

Recent structured turn history:
{self._history_text()}

Current operator request:
{query}

Return only the schema-constrained context interpretation.

Context contract:
- relation is standalone or followup.
- inherit contains only missing semantic fields unambiguously referenced from prior state: intent, time, policy, objective, constraints.
- relative_time.offset_minutes is present only when the current utterance expresses time relative to an inherited timestamp.
- Do not calculate the resulting clock time. Python performs clock arithmetic.
- Explicit current-turn information overrides inherited state.
- A standalone request must not inherit previous state.
- If the current turn continues the same analytical request while changing only time/arguments, inherit intent.
- If the current turn explicitly changes analytical intent, do not inherit intent; inherit only referenced fields such as time.
- Do not invent missing reference values.
"""

        attempts: list[dict[str, Any]] = []
        schema = self._output_schema()
        for attempt_no in (1, 2):
            payload = {
                "model": config.OLLAMA_MODEL,
                "prompt": prompt if attempt_no == 1 else prompt + "\nThe previous context object failed validation. Return only a schema-valid context object.",
                "stream": False,
                "format": schema,
                "options": {"temperature": 0, "num_predict": 180},
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
                decision = self._validate_decision(selected)
                self.last_audit = {
                    "prompt_version": config.prompt_version("coordinator"),
                    "attempts": attempts + [{"attempt": attempt_no, "ok": True, "raw": raw_text}],
                    "parse_failed": False,
                    "fallback_used": False,
                    "context": {
                        "relation": decision.context.relation,
                        "inherit": list(decision.context.inherit),
                        "relative_time_offset_minutes": decision.context.relative_time_offset_minutes,
                    },
                }
                return decision
            except Exception as exc:
                attempts.append({"attempt": attempt_no, "ok": False, "error": f"{type(exc).__name__}: {exc}"})

        fallback = CoordinatorDecision(context=ContextInterpretation(), handoffs=[])
        self.last_audit = {
            "prompt_version": config.prompt_version("coordinator"),
            "attempts": attempts,
            "parse_failed": True,
            "fallback_used": True,
            "context": {"relation": "standalone", "inherit": [], "relative_time_offset_minutes": None},
        }
        return fallback

    @staticmethod
    def _output_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "context": {
                    "type": "object",
                    "properties": {
                        "relation": {"type": "string", "enum": ["standalone", "followup"]},
                        "inherit": {
                            "type": "array",
                            "items": {"type": "string", "enum": CONTEXT_FIELDS},
                            "uniqueItems": True,
                        },
                        "relative_time": {
                            "type": "object",
                            "properties": {
                                "offset_minutes": {"type": "integer", "minimum": -1440, "maximum": 1440},
                            },
                            "required": ["offset_minutes"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["relation", "inherit"],
                    "additionalProperties": False,
                },
            },
            "required": ["context"],
            "additionalProperties": False,
        }

    @staticmethod
    def _parse_json(raw_text: str) -> dict[str, Any]:
        if not raw_text:
            raise ValueError("empty model response")
        value = json.loads(raw_text)
        if not isinstance(value, dict):
            raise ValueError("structured response must be an object")
        return value

    @staticmethod
    def _validate_decision(selected: dict[str, Any]) -> CoordinatorDecision:
        raw_context = selected.get("context")
        if not isinstance(raw_context, dict):
            raise ValueError("context must be an object")

        relation = raw_context.get("relation")
        if relation not in {"standalone", "followup"}:
            raise ValueError("invalid context relation")

        raw_inherit = raw_context.get("inherit", [])
        if not isinstance(raw_inherit, list) or any(x not in CONTEXT_FIELDS for x in raw_inherit):
            raise ValueError("invalid context inheritance")
        inherit = list(dict.fromkeys(str(x) for x in raw_inherit))

        offset: int | None = None
        relative = raw_context.get("relative_time")
        if relative is not None:
            if not isinstance(relative, dict) or not isinstance(relative.get("offset_minutes"), int):
                raise ValueError("invalid relative time")
            offset = int(relative["offset_minutes"])
            if not -1440 <= offset <= 1440:
                raise ValueError("relative time offset out of bounds")

        if relation == "standalone":
            inherit = []
            offset = None
        elif offset is not None and "time" not in inherit:
            raise ValueError("relative time requires inherited time")

        return CoordinatorDecision(
            context=ContextInterpretation(
                relation=relation,
                inherit=inherit,
                relative_time_offset_minutes=offset,
            ),
            handoffs=[],
        )

    def record_turn(
        self,
        query: str,
        handoffs: list[str],
        steps: list[dict[str, Any]],
        evidence: dict[str, Any],
        answer: str,
    ) -> None:
        self.history.append({
            "query": query,
            "handoffs": list(handoffs),
            "steps": steps,
            "evidence_summary": self._compact_evidence(evidence),
        })
        self.history = self.history[-8:]

    def reset(self) -> None:
        self.history.clear()
        self.last_audit = {}

    def _history_text(self) -> str:
        if not self.history:
            return "(none)"
        return "\n".join(json.dumps(item, ensure_ascii=False) for item in self.history[-4:])

    @staticmethod
    def _compact_memory(memory: dict[str, Any]) -> dict[str, Any]:
        keep = {
            "last_time", "last_tool", "last_agent", "last_policy", "recommended_policy",
            "last_objective", "last_constraints_raw", "comparison_time_a", "comparison_time_b",
        }
        return {k: memory[k] for k in keep if k in memory}

    @staticmethod
    def _compact_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        keep = {"category", "timestamp", "time_a", "time_b", "recommended_policy", "policy", "objective"}
        result = {k: v for k, v in evidence.items() if k in keep}
        if "final" in evidence and isinstance(evidence["final"], dict):
            result["final"] = {k: evidence["final"].get(k) for k in keep if k in evidence["final"]}
        return result
