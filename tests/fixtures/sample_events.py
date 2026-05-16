"""Canned SSE event payloads for tests."""

from __future__ import annotations


def chunk(flavor: str = "assistant", text: str = "hi") -> dict:
    return {"type": "AgentChunkEvent", "flavor": flavor, "text": text, "at": 0}


def thinking(flavor: str = "assistant", text: str = "let me think") -> dict:
    return {"type": "AgentThinkingEvent", "flavor": flavor, "text": text, "at": 0}


def turn_done(flavor: str = "assistant", stop_reason: str = "end_turn") -> dict:
    return {
        "type": "AgentTurnDoneEvent",
        "flavor": flavor,
        "stop_reason": stop_reason,
        "at": 0,
        "token_usage": {"input": 100, "output": 50, "total": 150},
    }


def tool_started(
    flavor: str = "assistant", tool: str = "bash", args: str = "ls", call_id: str = "t1"
) -> dict:
    return {
        "type": "ToolCallEvent",
        "flavor": flavor,
        "tool": tool,
        "title": args,
        "status": "started",
        "call_id": call_id,
        "at": 0,
    }


def tool_completed(flavor: str = "assistant", tool: str = "bash", call_id: str = "t1") -> dict:
    return {
        "type": "ToolCallEvent",
        "flavor": flavor,
        "tool": tool,
        "title": "ls",
        "status": "completed",
        "call_id": call_id,
        "at": 0,
    }


def skill_loaded(flavor: str = "assistant", name: str = "test-skill", size: int = 2048) -> dict:
    return {
        "type": "SkillLoadedEvent",
        "flavor": flavor,
        "skill_name": name,
        "skill_size": size,
        "at": 0,
    }


def flavor_status(flavor: str = "assistant", status: str = "running") -> dict:
    return {"type": "FlavorStatusEvent", "flavor": flavor, "status": status, "at": 0}


def permission_required(
    flavor: str = "assistant",
    tool: str = "bash",
    permission_id: str = "p1",
    risk: str = "medium",
) -> dict:
    return {
        "type": "PermissionRequiredEvent",
        "flavor": flavor,
        "tool": tool,
        "permission_id": permission_id,
        "risk": risk,
        "args": {"command": "rm -rf /"},
        "description": "Dangerous",
        "at": 0,
    }
