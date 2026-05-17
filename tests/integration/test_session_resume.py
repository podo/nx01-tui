"""Resume-session replay tests (W7 of podo/nx01-tui#26).

The frontend half of nx01#94. When the user picks Resume in SessionsModal:
- the conversation is wiped + replayed from the DB row stream
- thinking blocks (reasoning) are rendered, collapsed
- tool calls + tool output are reconciled by call_id
- _active_session_id[flavor] is set so the next send appends
- cross-flavor: tab auto-switches first
"""

from __future__ import annotations

import pytest

from nx01_tui.tui.app import Nx01App
from nx01_tui.tui.modals.sessions_modal import SessionAction
from nx01_tui.tui.widgets import (
    AssistantMessage,
    ThinkingBlock,
    ToolCallBlock,
    UserMessage,
)


async def _settle(app, pilot, secs: float = 1.0) -> None:
    await pilot.pause(secs)
    for w in list(app.workers):
        w.cancel()
    await pilot.pause(0.2)


def _stub_messages() -> list[dict]:
    """A representative row stream: user → assistant(reasoning + content +
    tool_calls) → tool(output)."""
    return [
        {"role": "user", "content": "Run ls", "timestamp": 1},
        {
            "role": "assistant",
            "content": "Sure, running ls.",
            "reasoning": "user wants directory listing",
            "tool_calls": [{"id": "t1", "name": "bash", "arguments": "ls -la"}],
            "timestamp": 2,
        },
        {
            "role": "tool",
            "tool_name": "bash",
            "tool_call_id": "t1",
            "content": "file_a\nfile_b\n",
            "timestamp": 3,
        },
    ]


@pytest.mark.asyncio
async def test_resume_replays_history_into_conversation(monkeypatch):
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)

        async def fake_resume(_sid):
            return {"session": {"id": _sid, "flavor": "assistant"}}

        async def fake_get_msgs(_sid, flavor=None):
            return _stub_messages()

        monkeypatch.setattr(app.client, "resume_session", fake_resume)
        monkeypatch.setattr(app.client, "get_session_messages", fake_get_msgs)

        await app._resume_session(
            SessionAction("resume", session_id="sess_abc", flavor="assistant")
        )
        await pilot.pause(0.2)

        pane = app._panes["assistant"]
        conv = pane.conversation
        # User message rendered
        assert len(conv.query(UserMessage)) == 1
        # One assistant message
        assert len(conv.query(AssistantMessage)) == 1
        # Thinking block from reasoning column — collapsed
        thinking = conv.query(ThinkingBlock)
        assert len(thinking) == 1
        assert thinking.first().has_class("collapsed")
        # Tool call block reconciled with tool-output row
        tools = conv.query(ToolCallBlock)
        assert len(tools) == 1
        # Active session id tracked for next send
        assert app._active_session_id["assistant"] == "sess_abc"


@pytest.mark.asyncio
async def test_resume_clears_existing_conversation(monkeypatch):
    """Pre-existing content gets wiped before replay."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)

        # Seed with one old turn
        app._panes["assistant"].conversation.add_user_message("stale chat")
        await pilot.pause(0.05)

        async def fake_resume(_sid):
            return {"session": {"id": _sid}}

        async def fake_get_msgs(_sid, flavor=None):
            return [{"role": "user", "content": "fresh resume msg", "timestamp": 1}]

        monkeypatch.setattr(app.client, "resume_session", fake_resume)
        monkeypatch.setattr(app.client, "get_session_messages", fake_get_msgs)
        await app._resume_session(SessionAction("resume", session_id="sess_x", flavor="assistant"))
        await pilot.pause(0.2)

        # Old "stale chat" gone, only the new one rendered.
        conv = app._panes["assistant"].conversation
        users = conv.query(UserMessage)
        assert len(users) == 1


@pytest.mark.asyncio
async def test_resume_auto_switches_tab_for_cross_flavor(monkeypatch):
    app = Nx01App("http://localhost:9999", flavors=["assistant", "operator"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        # Currently on assistant
        assert app._active_flavor() == "assistant"

        async def fake_resume(_sid):
            return {"session": {"id": _sid}}

        async def fake_get_msgs(_sid, flavor=None):
            return [{"role": "user", "content": "op msg", "timestamp": 1}]

        monkeypatch.setattr(app.client, "resume_session", fake_resume)
        monkeypatch.setattr(app.client, "get_session_messages", fake_get_msgs)

        # Resume a session that lives in the operator flavor.
        await app._resume_session(SessionAction("resume", session_id="sess_op", flavor="operator"))
        await pilot.pause(0.2)
        # Tab switched
        assert app._active_flavor() == "operator"
        # And the operator pane has the replayed message.
        conv = app._panes["operator"].conversation
        assert len(conv.query(UserMessage)) == 1


@pytest.mark.asyncio
async def test_next_send_passes_active_session_id(monkeypatch):
    """After resume, the next send_message call carries session_id."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        app._active_session_id["assistant"] = "sess_xyz"

        captured: dict = {}

        async def fake_send(flavor, text, session_id=None):
            captured["flavor"] = flavor
            captured["text"] = text
            captured["session_id"] = session_id
            return {"correlation_id": "c1", "session_id": "sess_xyz"}

        monkeypatch.setattr(app.client, "send_message", fake_send)
        await app._send_message("assistant", "hello")
        assert captured["session_id"] == "sess_xyz"
