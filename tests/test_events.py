"""Unit tests for SSE event parser."""

from __future__ import annotations

from nx01_tui.tui.events import (
    AgentChunkEvent,
    AgentTurnDoneEvent,
    PermissionRequiredEvent,
    SkillLoadedEvent,
    SseEvent,
    ToolCallEvent,
    parse_event,
)


def test_parse_chunk():
    e = parse_event({"type": "AgentChunkEvent", "flavor": "assistant", "text": "hi"})
    assert isinstance(e, AgentChunkEvent)
    assert e.text == "hi"
    assert e.flavor == "assistant"


def test_parse_turn_done_with_token_usage():
    e = parse_event(
        {
            "type": "AgentTurnDoneEvent",
            "flavor": "x",
            "stop_reason": "end",
            "token_usage": {"input": 1, "output": 2, "total": 3},
        }
    )
    assert isinstance(e, AgentTurnDoneEvent)
    assert e.token_usage["total"] == 3


def test_parse_tool_call_preserves_call_id():
    e = parse_event(
        {
            "type": "ToolCallEvent",
            "flavor": "x",
            "tool": "bash",
            "status": "started",
            "call_id": "abc",
        }
    )
    assert isinstance(e, ToolCallEvent)
    assert e.raw["call_id"] == "abc"


def test_parse_skill_loaded():
    e = parse_event(
        {"type": "SkillLoadedEvent", "flavor": "x", "skill_name": "s", "skill_size": 10}
    )
    assert isinstance(e, SkillLoadedEvent)
    assert e.skill_name == "s"


def test_parse_permission_required():
    e = parse_event(
        {
            "type": "PermissionRequiredEvent",
            "flavor": "x",
            "permission_id": "p",
            "tool": "bash",
            "risk": "high",
        }
    )
    assert isinstance(e, PermissionRequiredEvent)
    assert e.risk == "high"


def test_unknown_event_falls_back_to_base():
    e = parse_event({"type": "UnknownEventType", "flavor": "x", "at": 1.5})
    assert isinstance(e, SseEvent)
    assert e.type == "UnknownEventType"
    assert e.flavor == "x"
    assert e.at == 1.5
