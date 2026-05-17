"""End-to-end interaction tests covering App action methods.

These hit the `action_*` methods + message handlers directly to lift
coverage on app.py.
"""

from __future__ import annotations

import pytest

from nx01_tui.tui.app import ConnectionStatusMessage, Nx01App, SseMessage
from nx01_tui.tui.events import parse_event
from nx01_tui.tui.state import AgentState
from nx01_tui.tui.widgets import (
    AppHeader,
    ChatInput,
    SearchBar,
    SlashDropdown,
    StatusBar,
)
from tests.fixtures.sample_events import chunk, permission_required, thinking, turn_done


async def _settle(app, pilot, secs: float = 1.0) -> None:
    """Pause for mount + cancel SSE workers so retries don't race tests."""
    await pilot.pause(secs)
    for w in list(app.workers):
        w.cancel()
    await pilot.pause(0.2)


@pytest.mark.asyncio
async def test_connection_status_message_updates_header():
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        hdr = app.query_one(AppHeader)

        app.post_message(ConnectionStatusMessage("connected"))
        await pilot.pause(0.1)
        assert hdr.connected is True
        assert hdr.reconnecting is False

        app.post_message(ConnectionStatusMessage("reconnecting", "1"))
        await pilot.pause(0.1)
        assert hdr.reconnecting is True

        app.post_message(ConnectionStatusMessage("disconnected", "lost"))
        await pilot.pause(0.1)
        assert hdr.connected is False
        assert hdr.reconnecting is False


@pytest.mark.asyncio
async def test_sse_message_routes_to_dispatcher():
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        app.post_message(SseMessage(parse_event(chunk(text="streaming chunk"))))
        await pilot.pause(0.1)
        state = app._states["assistant"]
        assert state.state == AgentState.STREAMING


@pytest.mark.asyncio
async def test_on_chat_input_submitted_drives_send():
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        sent: list[str] = []

        async def fake_send(flavor: str, text: str, session_id: str | None = None):
            sent.append(f"{flavor}:{text}")
            return {"correlation_id": "c1"}

        app.client.send_message = fake_send  # type: ignore[method-assign]

        app.on_chat_input_submitted(ChatInput.Submitted("hello"))
        await pilot.pause(0.2)
        assert sent and sent[0].endswith(":hello")
        # `set_state` puts the CSS class on the pane immediately.
        assert app._panes["assistant"].has_class("thinking")


@pytest.mark.asyncio
async def test_slash_dropdown_completed_writes_input():
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        app.on_slash_dropdown_completed(SlashDropdown.Completed("/memory"))
        await pilot.pause(0.05)
        inp = app.query_one("#input-assistant", ChatInput)
        assert inp.text.startswith("/memory")


@pytest.mark.asyncio
async def test_action_toggle_sidebar_flips_class():
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        pane = app._panes["assistant"]
        assert not pane.sidebar.has_class("hidden")
        app.action_toggle_sidebar()
        assert pane.sidebar.has_class("hidden")
        app.action_toggle_sidebar()
        assert not pane.sidebar.has_class("hidden")


@pytest.mark.asyncio
async def test_action_search_shows_search_bar():
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        app.action_search()
        await pilot.pause(0.05)
        bar = app.query_one("#search-assistant", SearchBar)
        assert bar.has_class("visible")


@pytest.mark.asyncio
async def test_action_switch_flavor_rotates_tabs():
    app = Nx01App("http://localhost:9999", flavors=["a", "b", "c"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        active_before = app._active_flavor()
        app.action_switch_flavor()
        await pilot.pause(0.05)
        assert app._active_flavor() != active_before


@pytest.mark.asyncio
async def test_action_yank_focused_copies_last_chunk(monkeypatch):
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        copied: list[str] = []
        monkeypatch.setattr(app, "copy_to_clipboard", lambda txt: copied.append(txt))
        app._states["assistant"].messages.append({"type": "chunk", "text": "response body"})
        app.action_yank_focused()
        assert copied == ["response body"]


@pytest.mark.asyncio
async def test_action_yank_last_code(monkeypatch):
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        copied: list[str] = []
        monkeypatch.setattr(app, "copy_to_clipboard", lambda txt: copied.append(txt))
        app._states["assistant"].messages.append(
            {"type": "chunk", "text": "intro\n```py\nprint('hi')\n```\noutro"}
        )
        app.action_yank_last_code()
        assert copied == ["print('hi')"]


@pytest.mark.asyncio
async def test_action_new_session_clears_state():
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        app._states["assistant"].messages.append({"type": "chunk", "text": "old"})
        await app.action_new_session()
        assert app._states["assistant"].messages == []


@pytest.mark.asyncio
async def test_status_bar_follows_active_tab():
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        app._dispatch_event(parse_event(thinking()))
        await pilot.pause(0.1)
        bar = app.query_one(StatusBar)
        assert bar.state == AgentState.THINKING

        app._dispatch_event(parse_event(turn_done()))
        await pilot.pause(0.1)
        assert bar.state == AgentState.DONE


@pytest.mark.asyncio
async def test_on_resize_applies_sidebar_classes():
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        sb = app._panes["assistant"].sidebar
        sb.apply_terminal_width(80)
        assert sb.has_class("hidden")
        sb.apply_terminal_width(200)
        assert not sb.has_class("hidden")


@pytest.mark.asyncio
async def test_always_allow_set_skips_modal(monkeypatch):
    """An `always_allow` tool short-circuits the modal."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        resolved: list[tuple[str, str]] = []

        async def fake_resolve(permission_id: str, decision: str) -> None:
            resolved.append((permission_id, decision))

        monkeypatch.setattr(app.client, "resolve_permission", fake_resolve)
        app._always_allow_tools.add("bash")
        app._dispatch_event(parse_event(permission_required(tool="bash", permission_id="p1")))
        await _settle(app, pilot)
        assert ("p1", "allow") in resolved
        # No modal was pushed.
        assert app.screen.__class__.__name__ != "PermissionModal"
