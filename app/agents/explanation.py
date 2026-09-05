from __future__ import annotations

import json
import re
from typing import Any
from urllib.request import Request, urlopen

from app import config


class ExplanationAgent:
    def explain(
        self,
        query: str,
        evidence: dict[str, Any],
        fallback: str,
        strict_operational: bool = True,
    ) -> str:
        # Conference mode: the LLM coordinates tools, but technical evidence is
        # rendered deterministically so fields cannot be relabelled or truncated.
        if strict_operational:
            return fallback
        prompt = f"""You are the explanation agent for a coherent P2MP SLA digital twin.
Answer the operator in at most 120 words using only the validated evidence.
Preserve numbers and times exactly. Recommendations are advisory and require operator approval.
If evidence contains uncertainty or warnings, state them. Do not claim an action was executed.
Use Gbps exactly; never write GBps. A state distribution is a percentage of forecast
intervals, not the probability or chance of a state. For a service-peak or ranking
question, discuss only the requested service and the returned times and loads.
Question: {query}
Validated evidence: {json.dumps(evidence, ensure_ascii=False)}"""
        try:
            payload = {"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0.1, "num_predict": 180}}
            request = Request(f"{config.OLLAMA_URL}/api/generate", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=60) as response:
                candidate = json.loads(response.read())["response"].strip()
            valid = self._numbers_are_grounded(candidate, evidence)
            valid = valid and self._semantics_are_grounded(candidate, evidence)
            return candidate if valid else fallback
        except Exception:
            return fallback

    @staticmethod
    def _numbers_are_grounded(answer: str, evidence: dict[str, Any]) -> bool:
        """Reject an explanation that introduces unsupported numeric claims."""
        answer_numbers = [float(x) for x in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", answer)]
        evidence_numbers = [
            float(x) for x in re.findall(
                r"(?<![A-Za-z])\d+(?:\.\d+)?", json.dumps(evidence, ensure_ascii=False)
            )
        ]
        return all(any(abs(value - allowed) < 1e-6 for allowed in evidence_numbers) for value in answer_numbers)

    @staticmethod
    def _semantics_are_grounded(answer: str, evidence: dict[str, Any]) -> bool:
        lower = answer.lower()
        if "gbps" in lower and "GBps" in answer:
            return False
        if "state_distribution_percent" in evidence:
            bad = re.search(
                r"(?:chance|probability)\s+(?:of\s+)?(?:normal|degraded|failure[-_ ]?prone)",
                lower,
            )
            if bad:
                return False
        requested = evidence.get("service")
        if requested and "service_load_gbps" in json.dumps(evidence):
            other_services = {"ENTERPRISE", "RAN", "PON"} - {str(requested).upper()}
            if any(re.search(rf"\b{name}\b", answer.upper()) for name in other_services):
                return False
        return True
