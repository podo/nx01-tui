"""SSE event dataclasses for the nx01 API event stream.

Each event mirrors the JSON payload the nx01 server emits on `GET /events`.
Parsing is lenient: unknown fields are ignored, missing fields default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SseEvent:
    """Base SSE event — every event has a type, flavor, and timestamp."""

    type: str
    flavor: str = ""
    at: float = 0.0
    correlation_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class FlavorStatusEvent(SseEvent):
    status: str = "idle"  # started|stopped|crashed|failed|reloaded|running|idle


@dataclass
class HeartbeatEvent(SseEvent):
    pass


@dataclass
class AgentChunkEvent(SseEvent):
    session_id: str = ""
    text: str = ""


@dataclass
class AgentThinkingEvent(SseEvent):
    session_id: str = ""
    text: str = ""


@dataclass
class AgentTurnDoneEvent(SseEvent):
    session_id: str = ""
    stop_reason: str = ""
    token_usage: dict[str, int] = field(default_factory=dict)  # input/output/total


@dataclass
class ToolCallEvent(SseEvent):
    tool: str = ""
    title: str = ""
    status: str = ""  # started|completed|error|pending|in_progress|failed
    session_id: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    output: str = ""


@dataclass
class SkillLoadedEvent(SseEvent):
    """Emitted when Hermes loads a skill into a session."""

    skill_name: str = ""
    skill_size: int = 0
    session_id: str = ""


@dataclass
class PermissionRequiredEvent(SseEvent):
    """Backend requests user approval for a tool call."""

    permission_id: str = ""
    tool: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    risk: str = "low"  # low|medium|high
    description: str = ""


@dataclass
class ScheduledTaskEvent(SseEvent):
    job_id: str = ""
    state: str = ""


_EVENT_TYPES: dict[str, type[SseEvent]] = {
    "FlavorStatusEvent": FlavorStatusEvent,
    "HeartbeatEvent": HeartbeatEvent,
    "AgentChunkEvent": AgentChunkEvent,
    "AgentThinkingEvent": AgentThinkingEvent,
    "AgentTurnDoneEvent": AgentTurnDoneEvent,
    "ToolCallEvent": ToolCallEvent,
    "SkillLoadedEvent": SkillLoadedEvent,
    "PermissionRequiredEvent": PermissionRequiredEvent,
    "ScheduledTaskEvent": ScheduledTaskEvent,
}


def parse_event(payload: dict[str, Any]) -> SseEvent:
    """Parse a JSON dict into the matching dataclass.

    Falls back to a generic SseEvent when the type is unknown so the
    caller can still log/inspect it. Field access is defensive — any
    missing key uses the dataclass default.
    """
    kind = payload.get("type", "")
    cls = _EVENT_TYPES.get(kind, SseEvent)
    common = {
        "type": kind,
        "flavor": payload.get("flavor", ""),
        "at": float(payload.get("at", 0.0)),
        "correlation_id": payload.get("correlation_id"),
        "raw": payload,
    }
    if cls is SseEvent:
        return SseEvent(**common)

    specific: dict[str, Any] = {}
    for fld in cls.__dataclass_fields__.values():
        if fld.name in common:
            continue
        if fld.name in payload:
            specific[fld.name] = payload[fld.name]
    return cls(**common, **specific)
