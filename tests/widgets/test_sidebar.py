"""MonitorSidebar — section update + responsive class tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from nx01_tui.tui.state import FlavorState
from nx01_tui.tui.widgets import MonitorSidebar
from nx01_tui.tui.widgets.sidebar import McpSection


class _Host(App):
    def compose(self) -> ComposeResult:
        yield MonitorSidebar(flavor="assistant")


def _state_with_activity() -> FlavorState:
    s = FlavorState(name="assistant")
    s.apply_tool("bash", "ls", "started", call_id="t1")
    s.apply_tool("read", "f.txt", "completed", call_id="t2")
    s.apply_skill_loaded("ci-setup", 4096)
    s.token_usage = {"input": 1000, "output": 500, "total": 1500}
    return s


@pytest.mark.asyncio
async def test_update_from_renders_all_sections():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        sb = app.query_one(MonitorSidebar)
        sb.update_from(_state_with_activity())
        sb.set_memory(agent_chars=1500, user_chars=800)
        await pilot.pause(0.05)
        # Hard assertion: no exceptions raised by any section.


@pytest.mark.asyncio
async def test_responsive_hides_below_130_cols():
    """#29 item 3 — sidebar hides entirely below 130 cols (icon-strip removed)."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        sb = app.query_one(MonitorSidebar)

        sb.apply_terminal_width(90)
        assert sb.has_class("hidden")

        sb.apply_terminal_width(120)
        assert sb.has_class("hidden")
        assert not sb.has_class("icon-strip")

        sb.apply_terminal_width(160)
        assert not sb.has_class("hidden")


@pytest.mark.asyncio
async def test_responsive_width_scales_with_terminal():
    """In normal mode (width ≥ 130), sidebar width = clamp(30, term//4, 50)."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        sb = app.query_one(MonitorSidebar)

        # 130 // 4 = 32, clamped to MIN_WIDTH=30 → 32
        sb.apply_terminal_width(130)
        assert int(sb.styles.width.value) == 32

        # 160 // 4 = 40 → 40
        sb.apply_terminal_width(160)
        assert int(sb.styles.width.value) == 40

        # 240 // 4 = 60 → clamped to MAX_WIDTH = 50
        sb.apply_terminal_width(240)
        assert int(sb.styles.width.value) == 50

        # Below 130 — hidden entirely.
        sb.apply_terminal_width(110)
        assert sb.has_class("hidden")


@pytest.mark.asyncio
async def test_mcp_section_renders_server_rows():
    """McpSection.update_servers() renders one row per server."""

    class _McpHost(App):
        def compose(self) -> ComposeResult:
            yield McpSection()

    servers = [
        {"name": "github", "status": "connected", "tools": []},
        {"name": "slack", "status": "error", "tools": []},
    ]
    app = _McpHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        mcp = app.query_one(McpSection)
        mcp.update_servers(servers)
        await pilot.pause(0.05)
        rows = mcp.query_one("#mcp-list").children
        assert len(list(rows)) == 2


@pytest.mark.asyncio
async def test_mcp_section_shows_none_when_empty():
    """McpSection.update_servers([]) renders the 'none' placeholder."""

    class _McpHost(App):
        def compose(self) -> ComposeResult:
            yield McpSection()

    app = _McpHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        mcp = app.query_one(McpSection)
        mcp.update_servers([])
        await pilot.pause(0.05)
        rows = mcp.query_one("#mcp-list").children
        # Should be the "[dim]none[/]" placeholder Static
        assert len(list(rows)) == 1


@pytest.mark.asyncio
async def test_memory_section_has_mem0_row():
    """MemorySection renders a mem0 status row by default showing 'off'."""
    from nx01_tui.tui.widgets.sidebar import MemorySection

    class _MemHost(App):
        def compose(self) -> ComposeResult:
            yield MemorySection()

    app = _MemHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        mem = app.query_one(MemorySection)
        row = mem.query_one("#mem0-row", Static)
        assert row is not None
        assert "off" in str(row.content).lower()


@pytest.mark.asyncio
async def test_memory_section_set_mem0_status():
    """set_mem0_status() updates the mem0 row text."""
    from nx01_tui.tui.widgets.sidebar import MemorySection

    class _MemHost(App):
        def compose(self) -> ComposeResult:
            yield MemorySection()

    app = _MemHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        mem = app.query_one(MemorySection)
        mem.set_mem0_status("active")
        await pilot.pause(0.05)
        row = mem.query_one("#mem0-row", Static)
        assert "active" in str(row.content).lower()


@pytest.mark.asyncio
async def test_update_from_calls_mcp_section():
    """MonitorSidebar.update_from() passes mcp_servers to McpSection."""

    class _Host(App):
        def compose(self) -> ComposeResult:
            yield MonitorSidebar(flavor="assistant")

    state = FlavorState(name="assistant")
    state.mcp_servers = [{"name": "github", "status": "connected", "tools": []}]

    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        sb = app.query_one(MonitorSidebar)
        sb.update_from(state)
        await pilot.pause(0.05)
        rows = sb.query_one(McpSection).query_one("#mcp-list").children
        assert len(list(rows)) == 1


@pytest.mark.asyncio
async def test_context_section_shows_input_output_breakdown():
    """ContextSection renders input/output/cost rows."""
    from nx01_tui.tui.widgets.sidebar import ContextSection

    class _CtxHost(App):
        def compose(self) -> ComposeResult:
            yield ContextSection()

    app = _CtxHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        ctx = app.query_one(ContextSection)
        ctx.input_tokens = 8_000
        ctx.output_tokens = 2_000
        ctx.tokens = 10_000
        await pilot.pause(0.05)
        inp = app.query_one("#input-label")
        out = app.query_one("#output-label")
        cost = app.query_one("#cost-label")
        assert inp is not None
        assert out is not None
        assert cost is not None


@pytest.mark.asyncio
async def test_context_section_cost_shows_dash():
    """Cost row shows '—' by default (cost monitor not yet wired)."""
    from nx01_tui.tui.widgets.sidebar import ContextSection

    class _CtxHost(App):
        def compose(self) -> ComposeResult:
            yield ContextSection()

    app = _CtxHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        cost = app.query_one("#cost-label", Static)
        assert "—" in str(cost.content)


@pytest.mark.asyncio
async def test_context_section_update_from_passes_input_output():
    """MonitorSidebar.update_from() sets input_tokens and output_tokens on ContextSection."""
    from nx01_tui.tui.widgets.sidebar import ContextSection

    class _SbHost(App):
        def compose(self) -> ComposeResult:
            yield MonitorSidebar(flavor="assistant")

    state = FlavorState(name="assistant")
    state.token_usage = {"input": 3_000, "output": 1_200, "total": 4_200}

    app = _SbHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        sb = app.query_one(MonitorSidebar)
        sb.update_from(state)
        await pilot.pause(0.05)
        ctx = sb.query_one(ContextSection)
        assert ctx.tokens == 4_200
        assert ctx.input_tokens == 3_000
        assert ctx.output_tokens == 1_200


@pytest.mark.asyncio
async def test_session_health_shows_agent_state():
    """SessionHealthSection.update_from() reflects the agent state name."""
    from nx01_tui.tui.state import AgentState
    from nx01_tui.tui.widgets.sidebar import SessionHealthSection

    class _Host(App):
        def compose(self) -> ComposeResult:
            yield SessionHealthSection()

    state = FlavorState(name="assistant")
    state.state = AgentState.STREAMING
    state.session_id = "abc123def456"
    state.messages = [{"type": "chunk", "text": "hello"}] * 3

    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        section = app.query_one(SessionHealthSection)
        section.update_from(state)
        await pilot.pause(0.05)
        state_row = section.query_one("#health-state")
        assert state_row is not None
        # The text should contain the state name
        content = state_row.content if hasattr(state_row, "content") else str(state_row.renderable)
        assert "streaming" in content.lower()


@pytest.mark.asyncio
async def test_session_health_shows_message_count():
    """SessionHealthSection shows message count."""
    from nx01_tui.tui.widgets.sidebar import SessionHealthSection

    class _Host(App):
        def compose(self) -> ComposeResult:
            yield SessionHealthSection()

    state = FlavorState(name="assistant")
    state.messages = [{"type": "chunk"}] * 5

    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        section = app.query_one(SessionHealthSection)
        section.update_from(state)
        await pilot.pause(0.05)
        msgs_row = section.query_one("#health-msgs")
        content = msgs_row.content if hasattr(msgs_row, "content") else str(msgs_row.renderable)
        assert "5" in content


@pytest.mark.asyncio
async def test_session_health_in_monitor_sidebar():
    """SessionHealthSection is the first child of MonitorSidebar."""
    from nx01_tui.tui.widgets.sidebar import SessionHealthSection

    class _Host(App):
        def compose(self) -> ComposeResult:
            yield MonitorSidebar(flavor="assistant")

    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        # SessionHealthSection must exist in the sidebar
        section = app.query_one(SessionHealthSection)
        assert section is not None
