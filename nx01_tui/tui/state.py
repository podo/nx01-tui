"""Per-flavor state machine + event routing for the TUI."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .events import (
    AgentChunkEvent,
    AgentThinkingEvent,
    AgentTurnDoneEvent,
    FlavorStatusEvent,
    PermissionRequiredEvent,
    SkillLoadedEvent,
    SseEvent,
    ToolCallEvent,
)


class AgentState(StrEnum):
    """High-level state of an agent flavor — drives all UI state-class flips."""

    IDLE = "idle"
    THINKING = "thinking"
    STREAMING = "streaming"
    TOOL_CALL = "tool_call"
    DONE = "done"
    ERROR = "error"


class ToolStatus(StrEnum):
    QUEUED = "queued"
    ACTIVE = "active"
    DONE = "done"
    ERROR = "error"


@dataclass
class ToolCall:
    """Snapshot of one tool call in the conversation timeline."""

    tool: str
    args: str = ""
    status: ToolStatus = ToolStatus.QUEUED
    output: str = ""
    elapsed_ms: int = 0
    started_at: float = field(default_factory=time.monotonic)
    call_id: str = ""

    def elapsed_str(self) -> str:
        if self.status in (ToolStatus.DONE, ToolStatus.ERROR):
            return f"{self.elapsed_ms / 1000:.1f}s"
        live = (time.monotonic() - self.started_at) * 1000
        return f"{live / 1000:.1f}s"


@dataclass
class FlavorState:
    """All in-memory state for a single flavor tab."""

    name: str
    state: AgentState = AgentState.IDLE
    status: str = "idle"  # backend FlavorStatusEvent
    messages: list[dict[str, Any]] = field(default_factory=list)
    thinking_lines: list[str] = field(default_factory=list)
    thinking_active: bool = False
    thinking_started_at: float = 0.0
    thinking_duration_ms: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)
    last_turn_tools: list[ToolCall] = field(default_factory=list)
    skills_loaded: list[dict[str, Any]] = field(default_factory=list)
    token_usage: dict[str, int] = field(
        default_factory=lambda: {"input": 0, "output": 0, "total": 0}
    )
    session_id: str = ""
    session_title: str = ""
    scroll_locked: bool = False
    error_message: str = ""

    # ── Event handlers (mutators) ────────────────────────────────────

    def apply_chunk(self, text: str) -> None:
        """Append streamed token to the active assistant message."""
        self.state = AgentState.STREAMING
        if self.messages and self.messages[-1]["type"] == "chunk":
            self.messages[-1]["text"] += text
        else:
            self.messages.append({"type": "chunk", "text": text, "author": "agent"})

    def apply_thinking(self, text: str) -> None:
        if not self.thinking_active:
            self.thinking_started_at = time.monotonic()
        self.state = AgentState.THINKING
        self.thinking_active = True
        self.thinking_lines.append(text)

    def seal_thinking(self) -> None:
        if self.thinking_lines:
            self.thinking_duration_ms = int((time.monotonic() - self.thinking_started_at) * 1000)
            self.messages.append(
                {
                    "type": "thinking_block",
                    "lines": list(self.thinking_lines),
                    "duration_ms": self.thinking_duration_ms,
                }
            )
        self.thinking_lines = []
        self.thinking_active = False

    def apply_tool(self, tool: str, args: str, status: str, call_id: str = "") -> ToolCall:
        """Create or update a tool call by call_id."""
        existing = next((tc for tc in self.tool_calls if tc.call_id == call_id and call_id), None)
        if existing is None:
            existing = ToolCall(
                tool=tool, args=args, call_id=call_id or f"{tool}-{len(self.tool_calls)}"
            )
            self.tool_calls.append(existing)

        backend_status = status.lower()
        if backend_status in ("started", "in_progress", "pending"):
            existing.status = ToolStatus.ACTIVE
            self.state = AgentState.TOOL_CALL
        elif backend_status == "completed":
            existing.status = ToolStatus.DONE
            existing.elapsed_ms = int((time.monotonic() - existing.started_at) * 1000)
        elif backend_status in ("error", "failed"):
            existing.status = ToolStatus.ERROR
            existing.elapsed_ms = int((time.monotonic() - existing.started_at) * 1000)
        return existing

    def apply_skill_loaded(self, skill_name: str, skill_size: int) -> None:
        if not any(s["name"] == skill_name for s in self.skills_loaded):
            self.skills_loaded.append({"name": skill_name, "size": skill_size})
        self.messages.append({"type": "skill_block", "name": skill_name, "size": skill_size})

    def preload_skills(self, skills: list[dict[str, Any]]) -> None:
        """Populate skills_loaded from API data without adding a conversation message."""
        for skill in skills:
            name = skill.get("name", "")
            size = int(skill.get("size") or 0)
            if name and not any(s["name"] == name for s in self.skills_loaded):
                self.skills_loaded.append({"name": name, "size": size})

    def seal_turn(self, stop_reason: str = "", token_usage: dict[str, int] | None = None) -> None:
        self.seal_thinking()
        self.last_turn_tools = list(self.tool_calls)
        if token_usage:
            self.token_usage.update(token_usage)
        if stop_reason == "error":
            self.state = AgentState.ERROR
        else:
            self.state = AgentState.DONE

    def set_error(self, message: str) -> None:
        self.error_message = message
        self.state = AgentState.ERROR

    def clear_for_new_turn(self) -> None:
        self.tool_calls = []
        self.thinking_lines = []
        self.thinking_active = False
        self.error_message = ""

    # ── Computed properties ──────────────────────────────────────────

    @property
    def context_percent(self) -> float:
        # 200k default context window; refine when backend exposes it
        limit = 200_000
        return min(100.0, (self.token_usage.get("total", 0) / limit) * 100)

    def activity_summary(self) -> tuple[int, int, int]:
        """(done, active, queued) tool count for the current turn."""
        done = sum(1 for tc in self.tool_calls if tc.status == ToolStatus.DONE)
        active = sum(1 for tc in self.tool_calls if tc.status == ToolStatus.ACTIVE)
        queued = sum(1 for tc in self.tool_calls if tc.status == ToolStatus.QUEUED)
        return done, active, queued


# ── SSE event → state routing ────────────────────────────────────────


def route_event(state: FlavorState, event: SseEvent) -> None:
    """Apply one parsed SSE event to the matching FlavorState.

    Caller is responsible for picking the right FlavorState based on
    event.flavor before invoking this.
    """
    if isinstance(event, AgentChunkEvent):
        state.apply_chunk(event.text)
    elif isinstance(event, AgentThinkingEvent):
        state.apply_thinking(event.text)
    elif isinstance(event, AgentTurnDoneEvent):
        state.seal_turn(stop_reason=event.stop_reason, token_usage=event.token_usage)
        if event.session_id:
            state.session_id = event.session_id
    elif isinstance(event, ToolCallEvent):
        state.apply_tool(
            event.tool, event.title or "", event.status, call_id=event.raw.get("call_id", "")
        )
    elif isinstance(event, SkillLoadedEvent):
        state.apply_skill_loaded(event.skill_name, event.skill_size)
    elif isinstance(event, FlavorStatusEvent):
        state.status = event.status
    elif isinstance(event, PermissionRequiredEvent):
        # Caller (App) handles modal push; nothing to mutate here.
        pass


def route_legacy_dict(state: FlavorState, payload: dict[str, Any]) -> None:
    """Back-compat shim: legacy callers still pass dicts (cli.py /watch)."""
    from .events import parse_event

    event = parse_event(payload)
    if event.flavor and event.flavor != state.name:
        return
    route_event(state, event)
