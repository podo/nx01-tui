"""Per-flavor reactive state for the TUI."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FlavorState:
    name: str
    status: str = "idle"
    messages: list[dict] = field(default_factory=list)
    thinking_lines: list[str] = field(default_factory=list)
    thinking_active: bool = False
    tool_calls: list[dict] = field(default_factory=list)
    last_turn_tools: list[dict] = field(default_factory=list)
    scroll_locked: bool = False

    def apply_chunk(self, text: str) -> None:
        if self.messages and self.messages[-1]["type"] == "chunk":
            self.messages[-1]["text"] += text
        else:
            self.messages.append({"type": "chunk", "text": text, "author": "agent"})

    def apply_thinking(self, text: str) -> None:
        self.thinking_active = True
        self.thinking_lines.append(text)

    def seal_thinking(self) -> None:
        if self.thinking_lines:
            self.messages.append({"type": "thinking_block", "lines": list(self.thinking_lines)})
        self.thinking_lines = []
        self.thinking_active = False

    def apply_tool(self, tool: str, arg: str, status: str) -> None:
        self.tool_calls.append({"tool": tool, "arg": arg, "status": status})

    def seal_turn(self) -> None:
        self.seal_thinking()
        self.last_turn_tools = list(self.tool_calls)
        self.tool_calls = []


def route_event(state: FlavorState, payload: dict) -> None:
    """Apply one SSE event payload to the correct FlavorState."""
    if payload.get("flavor") != state.name:
        return
    kind = payload.get("type", "")
    if kind == "AgentChunkEvent":
        state.apply_chunk(payload.get("text", ""))
    elif kind == "AgentThinkingEvent":
        state.apply_thinking(payload.get("text", ""))
    elif kind == "AgentTurnDoneEvent":
        state.seal_turn()
    elif kind == "ToolCallEvent":
        state.apply_tool(
            payload.get("tool", "?"),
            payload.get("title") or payload.get("arg", ""),
            payload.get("status", ""),
        )
    elif kind == "FlavorStatusEvent":
        state.status = payload.get("status", state.status)
