"""Auto-resume on startup tests.

Verifies that when the TUI starts after a previous session was cancelled
(Ctrl+C / tab close / graceful quit), it reads _STATE_FILE and replays
the saved session into the conversation automatically.
"""

from __future__ import annotations

import json
import time

import pytest

from nx01_tui.tui import app as app_module
from nx01_tui.tui.app import Nx01App
from nx01_tui.tui.widgets import AssistantMessage, ThinkingBlock, ToolCallBlock, UserMessage


def _stub_messages() -> list[dict]:
    return [
        {"role": "user", "content": "Show files", "timestamp": 1},
        {
            "role": "assistant",
            "content": "Running ls.",
            "reasoning": "user wants file listing",
            "tool_calls": [{"id": "tc-aabbcc", "name": "bash", "arguments": "ls -la"}],
            "timestamp": 2,
        },
        {
            "role": "tool",
            "tool_name": "bash",
            "tool_call_id": "tc-aabbcc",
            "content": "file_a\nfile_b\n",
            "timestamp": 3,
        },
    ]


def _mock_client(app):
    async def fake_get_flavors():
        return {"assistant": {"name": "assistant", "model": "m"}}

    async def fake_list_commands():
        return []

    async def fake_list_skills(flavor=None):
        return []

    async def fake_get_tools(flavor=None):
        return {"tools": []}

    async def fake_resume(session_id):
        return {"session": {"id": session_id, "flavor": "assistant"}}

    async def fake_get_msgs(session_id, flavor=None):
        return _stub_messages()

    app.client.get_flavors = fake_get_flavors
    app.client.list_commands = fake_list_commands
    app.client.list_skills = fake_list_skills
    app.client.get_tools = fake_get_tools
    app.client.resume_session = fake_resume
    app.client.get_session_messages = fake_get_msgs


async def _settle(app, pilot, secs: float = 1.2) -> None:
    await pilot.pause(secs)
    for w in list(app.workers):
        w.cancel()
    await pilot.pause(0.2)


@pytest.mark.asyncio
async def test_auto_resume_replays_saved_session(tmp_path, monkeypatch):
    """App reads state file on boot and replays session into conversation."""
    state_file = tmp_path / "nx01_tui_state.json"
    state_file.write_text(
        json.dumps({
            "version": 1,
            "sessions": {
                "assistant": {"session_id": "sess_saved", "quit_ts": time.time() - 10}
            },
        })
    )
    monkeypatch.setattr(app_module, "_STATE_FILE", state_file)

    tui = Nx01App("http://mock", api_key="t", flavors=["assistant"])
    _mock_client(tui)

    async with tui.run_test() as pilot:
        await _settle(tui, pilot)

        conv = tui._panes["assistant"].conversation
        assert len(conv.query(UserMessage)) == 1
        assert len(conv.query(AssistantMessage)) == 1
        assert len(conv.query(ThinkingBlock)) == 1
        assert len(conv.query(ToolCallBlock)) == 1
        assert tui._active_session_id["assistant"] == "sess_saved"


@pytest.mark.asyncio
async def test_auto_resume_sets_active_session_id(tmp_path, monkeypatch):
    """After auto-resume, next send carries the resumed session_id."""
    state_file = tmp_path / "nx01_tui_state.json"
    state_file.write_text(
        json.dumps({
            "version": 1,
            "sessions": {
                "assistant": {"session_id": "sess_abc", "quit_ts": time.time() - 5}
            },
        })
    )
    monkeypatch.setattr(app_module, "_STATE_FILE", state_file)

    tui = Nx01App("http://mock", api_key="t", flavors=["assistant"])
    _mock_client(tui)

    captured: dict = {}

    async def fake_send(flavor, text, session_id=None):
        captured["session_id"] = session_id
        return {"correlation_id": "c1", "session_id": "sess_abc"}

    tui.client.send_message = fake_send

    async with tui.run_test() as pilot:
        await _settle(tui, pilot)
        await tui._send_message("assistant", "hello")

    assert captured.get("session_id") == "sess_abc"


@pytest.mark.asyncio
async def test_auto_resume_noop_when_no_state_file(tmp_path, monkeypatch):
    """No crash and no replay when state file is absent."""
    missing = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(app_module, "_STATE_FILE", missing)

    tui = Nx01App("http://mock", api_key="t", flavors=["assistant"])
    _mock_client(tui)

    async with tui.run_test() as pilot:
        await _settle(tui, pilot)

        conv = tui._panes["assistant"].conversation
        assert len(conv.query(UserMessage)) == 0
        assert tui._active_session_id.get("assistant") is None


@pytest.mark.asyncio
async def test_save_state_writes_session_id(tmp_path, monkeypatch):
    """_save_session_state() writes the active session to disk."""
    state_file = tmp_path / "nx01_tui_state.json"
    monkeypatch.setattr(app_module, "_STATE_FILE", state_file)

    tui = Nx01App("http://mock", api_key="t", flavors=["assistant"])
    _mock_client(tui)

    async with tui.run_test() as pilot:
        await _settle(tui, pilot)
        tui._active_session_id["assistant"] = "sess_xyz"
        tui._save_session_state()

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert data["version"] == 1
    assert data["sessions"]["assistant"]["session_id"] == "sess_xyz"


@pytest.mark.asyncio
async def test_save_state_called_on_unmount(tmp_path, monkeypatch):
    """on_unmount triggers _save_session_state so Ctrl+C also persists state."""
    state_file = tmp_path / "nx01_tui_state.json"
    monkeypatch.setattr(app_module, "_STATE_FILE", state_file)

    tui = Nx01App("http://mock", api_key="t", flavors=["assistant"])
    _mock_client(tui)

    async with tui.run_test() as pilot:
        await _settle(tui, pilot)
        tui._active_session_id["assistant"] = "sess_ctrl_c"
        # on_unmount fires when the context manager exits — no explicit call needed.

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert data["sessions"]["assistant"]["session_id"] == "sess_ctrl_c"
