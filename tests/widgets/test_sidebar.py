"""MonitorSidebar — section update + responsive class tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from nx01_tui.tui.state import FlavorState
from nx01_tui.tui.widgets import MonitorSidebar


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
