from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ToolStep:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryPlan:
    intent: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    source: str = "mistral-tool-plan"
    steps: list[ToolStep] = field(default_factory=list)


@dataclass
class AgentEvent:
    agent: str
    action: str
    status: str = "completed"
    detail: str = ""


@dataclass
class AgentResponse:
    answer: str
    raw_llm_answer: str | None
    plan: QueryPlan
    evidence: dict[str, Any]
    grounding_passed: bool
    grounding_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    trace: list[AgentEvent] = field(default_factory=list)
    routing_audit: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
