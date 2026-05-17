"""End-to-end devtools smoke test — exercises every V1 + V2 feature via Pilot.

Run with `make test` locally, or `pytest tests/integration/test_e2e_devtools_smoke.py`.

This is the canonical "does everything still work" check. If you change a
widget or modal, this should still pass without modification.
"""

from __future__ import annotations

import pytest

from nx01_tui.tui.app import ConnectionStatusMessage, Nx01App, SseMessage
from nx01_tui.tui.events import parse_event
from nx01_tui.tui.modals import (
    CommandModal,
    DebugModal,
    HelpModal,
    MemoryModal,
    SessionsModal,
)
from nx01_tui.tui.state import AgentState, ToolStatus
from nx01_tui.tui.widgets import (
    AppHeader,
    ChatInput,
    CodeBlock,
    FilePickerDropdown,
    FlavorPane,
    SearchBar,
    SlashDropdown,
    StatusBar,
    ThinkingBlock,
    ToolCallBlock,
)
from tests.fixtures.sample_events import (
    chunk,
    permission_required,
    skill_loaded,
    thinking,
    tool_completed,
    tool_started,
    turn_done,
)


# Boot the app with three flavors and a wide terminal so every section
# renders. Backend is unreachable on purpose — graceful degradation kicks in.
@pytest.fixture
async def app_with_pilot():
    app = Nx01App("http://localhost:65535", flavors=["assistant", "operator", "analyst"])
    async with app.run_test(size=(180, 50)) as pilot:
        # Long enough for bootstrap worker to finish on slow Linux CI.
        await pilot.pause(1.5)
        yield app, pilot


# ── Section 1 — V1 core layout ───────────────────────────────────────


@pytest.mark.asyncio
async def test_boot_renders_header_tabs_sidebar_status_bar(app_with_pilot):
    app, _ = app_with_pilot
    assert app.query_one(AppHeader) is not None
    assert app.query_one(StatusBar) is not None
    panes = app.query(FlavorPane)
    assert len(panes) == 3
    # Every pane has its sidebar (5 sections + MCP = 6).
    for pane in panes:
        assert pane.sidebar is not None


@pytest.mark.asyncio
async def test_full_turn_lifecycle_renders_all_block_types(app_with_pilot):
    app, pilot = app_with_pilot
    # Drive an entire turn: thinking → tool → skill → chunk → done.
    events = [
        thinking(text="Reasoning about CI setup…"),
        tool_started(tool="bash", args="ls -la", call_id="t1"),
        tool_completed(tool="bash", call_id="t1"),
        skill_loaded(name="ci-setup", size=2048),
        chunk(text="Here's the workflow:\n\n```yaml\nname: CI\non: [push]\n```"),
        turn_done(),
    ]
    for raw in events:
        app._dispatch_event(parse_event(raw))
    await pilot.pause(0.3)

    state = app._states["assistant"]
    assert state.state == AgentState.DONE
    assert state.tool_calls[0].status == ToolStatus.DONE
    assert state.skills_loaded[0]["name"] == "ci-setup"
    assert state.token_usage["total"] == 150

    # All three block widgets mounted in the conversation.
    pane = app._panes["assistant"]
    conv = pane.conversation
    assert len(conv.query(ThinkingBlock)) >= 1
    assert len(conv.query(ToolCallBlock)) >= 1
    # CodeBlock auto-split from the assistant fence.
    assert len(conv.query(CodeBlock)) >= 1


# ── Section 2 — Modals (push / dismiss via callback) ────────────────


@pytest.mark.asyncio
async def test_command_modal_opens_via_ctrl_p(app_with_pilot):
    app, pilot = app_with_pilot
    await pilot.press("ctrl+p")
    await pilot.pause(0.2)
    assert app.screen.__class__ is CommandModal
    await pilot.press("escape")
    await pilot.pause(0.1)
    assert app.screen.__class__ is not CommandModal


@pytest.mark.asyncio
async def test_help_modal_opens_via_question_mark(app_with_pilot):
    app, pilot = app_with_pilot
    # ChatInput auto-focuses on boot; call the action directly so the test
    # isn't sensitive to focus state.
    app.action_help()
    await pilot.pause(0.2)
    assert app.screen.__class__ is HelpModal


@pytest.mark.asyncio
async def test_sessions_modal_degrades_gracefully(app_with_pilot, monkeypatch):
    app, pilot = app_with_pilot

    async def empty_list_sessions():
        return []

    monkeypatch.setattr(app.client, "list_sessions", empty_list_sessions)
    app.action_open_sessions()
    await pilot.pause(0.4)
    assert app.screen.__class__ is SessionsModal


@pytest.mark.asyncio
async def test_memory_modal_degrades_gracefully(app_with_pilot, monkeypatch):
    app, pilot = app_with_pilot

    async def empty_read(_store):
        return []

    monkeypatch.setattr(app.client, "read_memory", empty_read)
    app.action_open_memory()
    await pilot.pause(0.4)
    assert app.screen.__class__ is MemoryModal


@pytest.mark.asyncio
async def test_debug_modal_opens_and_receives_live_events(app_with_pilot):
    app, pilot = app_with_pilot
    # Pump events through the SseMessage path so they land in _debug_buffer.
    for raw in [thinking(), turn_done()]:
        app.post_message(SseMessage(parse_event(raw)))
    await pilot.pause(0.2)
    app.action_open_debug()
    await pilot.pause(0.3)
    assert app.screen.__class__ is DebugModal
    # Modal seeded from app's debug buffer on open.
    assert len(app.screen._buffer) >= 2


# ── Section 3 — V2 input enhancements ───────────────────────────────


@pytest.mark.asyncio
async def test_slash_dropdown_appears_on_slash(app_with_pilot):
    app, pilot = app_with_pilot
    flavor = app._active_flavor()
    dropdown = app.query_one(f"#slash-{flavor}", SlashDropdown)
    dropdown.update_for_text("/mem")
    await pilot.pause(0.05)
    assert dropdown.has_class("visible")


@pytest.mark.asyncio
async def test_file_picker_appears_on_at_token(app_with_pilot, monkeypatch):
    app, pilot = app_with_pilot
    flavor = app._active_flavor()
    picker = app.query_one(f"#files-{flavor}", FilePickerDropdown)
    # Inject a deterministic candidate list (lazy-scanned otherwise).
    picker._candidates = ["api/server.py", "config.py", "README.md"]
    picker.update_for_text("look at @api")
    await pilot.pause(0.05)
    assert picker.has_class("visible")
    assert picker.option_count >= 1


@pytest.mark.asyncio
async def test_slash_completion_rewrites_input(app_with_pilot):
    app, pilot = app_with_pilot
    flavor = app._active_flavor()
    inp = app.query_one(f"#input-{flavor}", ChatInput)
    inp.text = "/m"
    app.on_slash_dropdown_completed(SlashDropdown.Completed("/memory"))
    await pilot.pause(0.05)
    assert inp.text == "/memory "


@pytest.mark.asyncio
async def test_file_completion_rewrites_input(app_with_pilot):
    app, pilot = app_with_pilot
    flavor = app._active_flavor()
    inp = app.query_one(f"#input-{flavor}", ChatInput)
    inp.text = "look at @api"
    app.on_file_picker_dropdown_completed(FilePickerDropdown.Completed("api/server.py"))
    await pilot.pause(0.05)
    assert inp.text == "look at @api/server.py "


# ── Section 4 — Click-to-copy + yank shortcuts ──────────────────────


@pytest.mark.asyncio
async def test_code_block_click_copies(app_with_pilot, monkeypatch):
    app, pilot = app_with_pilot
    copied: list[str] = []
    monkeypatch.setattr(app, "copy_to_clipboard", lambda t: copied.append(t))

    # Drive an assistant turn with code → CodeBlock auto-mounts.
    app._dispatch_event(parse_event(chunk(text="```py\nx = 1\n```")))
    app._dispatch_event(parse_event(turn_done()))
    await pilot.pause(0.3)

    blocks = app._panes["assistant"].conversation.query(CodeBlock)
    assert len(blocks) >= 1
    blocks.first().on_click()
    assert "x = 1" in copied[0]


@pytest.mark.asyncio
async def test_yank_last_code_action(app_with_pilot, monkeypatch):
    app, pilot = app_with_pilot
    copied: list[str] = []
    monkeypatch.setattr(app, "copy_to_clipboard", lambda t: copied.append(t))
    app._states["assistant"].messages.append(
        {"type": "chunk", "text": "intro\n```bash\nls -la\n```\ndone"}
    )
    app.action_yank_last_code()
    assert copied == ["ls -la"]


# ── Section 5 — Keybindings & navigation ────────────────────────────


@pytest.mark.asyncio
async def test_tab_cycles_flavors(app_with_pilot):
    app, pilot = app_with_pilot
    first = app._active_flavor()
    app.action_switch_flavor()
    await pilot.pause(0.1)
    assert app._active_flavor() != first


@pytest.mark.asyncio
async def test_ctrl_b_toggles_sidebar(app_with_pilot):
    app, pilot = app_with_pilot
    pane = app._panes[app._active_flavor()]
    assert not pane.sidebar.has_class("hidden")
    app.action_toggle_sidebar()
    assert pane.sidebar.has_class("hidden")
    app.action_toggle_sidebar()
    assert not pane.sidebar.has_class("hidden")


@pytest.mark.asyncio
async def test_ctrl_f_reveals_search(app_with_pilot):
    app, pilot = app_with_pilot
    flavor = app._active_flavor()
    app.action_search()
    await pilot.pause(0.05)
    assert app.query_one(f"#search-{flavor}", SearchBar).has_class("visible")


# ── Section 6 — Connection state propagation ────────────────────────


@pytest.mark.asyncio
async def test_connection_status_drives_header(app_with_pilot):
    app, pilot = app_with_pilot
    hdr = app.query_one(AppHeader)
    app.post_message(ConnectionStatusMessage("reconnecting", "1"))
    await pilot.pause(0.1)
    assert hdr.reconnecting is True
    app.post_message(ConnectionStatusMessage("connected"))
    await pilot.pause(0.1)
    assert hdr.connected is True
    assert hdr.reconnecting is False


# ── Section 7 — Permission flow (always_allow short-circuit) ────────


@pytest.mark.asyncio
async def test_always_allow_skips_modal(app_with_pilot, monkeypatch):
    app, pilot = app_with_pilot
    resolved: list[tuple[str, str]] = []

    async def fake_resolve(pid, decision):
        resolved.append((pid, decision))

    monkeypatch.setattr(app.client, "resolve_permission", fake_resolve)
    app._always_allow_tools.add("bash")
    app._dispatch_event(parse_event(permission_required(tool="bash", permission_id="p1")))
    await pilot.pause(0.3)
    assert ("p1", "allow") in resolved
    assert app.screen.__class__.__name__ != "PermissionModal"


# ── Section 8 — Responsive sidebar ──────────────────────────────────


@pytest.mark.asyncio
async def test_responsive_sidebar_buckets(app_with_pilot):
    app, _ = app_with_pilot
    sb = app._panes[app._active_flavor()].sidebar
    sb.apply_terminal_width(80)
    assert sb.has_class("hidden")
    sb.apply_terminal_width(120)
    assert not sb.has_class("hidden")
    assert sb.has_class("icon-strip")
    sb.apply_terminal_width(180)
    assert not sb.has_class("hidden")
    assert not sb.has_class("icon-strip")
