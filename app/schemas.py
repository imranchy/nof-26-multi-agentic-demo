from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class QueryPlan:
    intent: str = "network_summary"
    service: str | None = None
    state: str | None = None
    start_minute: int = 0
    end_minute: int = 1440
    top_k: int = 5
    needs_recovery: bool = False
    needs_diagnosis: bool = False
    source: str = "deterministic"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "QueryPlan":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in value.items() if k in allowed})


@dataclass
class AgentEvent:
    agent: str
    action: str
    status: str = "completed"
    detail: str = ""


@dataclass
class AgentResponse:
    answer: str
    plan: QueryPlan
    evidence: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    trace: list[AgentEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

