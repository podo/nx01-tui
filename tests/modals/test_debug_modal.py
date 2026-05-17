"""DebugModal tests — push, filter, pause."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from nx01_tui.tui.events import parse_event
from nx01_tui.tui.modals import DebugModal
from tests.fixtures.sample_events import chunk, tool_started, turn_done


class _Host(App):
    def compose(self) -> ComposeResult:
        yield Static("host")


@pytest.mark.asyncio
async def test_initial_buffer_renders():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        modal = DebugModal([parse_event(chunk(text="hi")), parse_event(tool_started())])
        await app.push_screen(modal)
        await pilot.pause(0.1)
        assert "2 events buffered" in str(modal.query_one("#event-counts", Static).render())


@pytest.mark.asyncio
async def test_push_appends_to_log():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        modal = DebugModal()
        await app.push_screen(modal)
        await pilot.pause(0.05)
        modal.push(parse_event(turn_done()))
        await pilot.pause(0.05)
        assert "1 events buffered" in str(modal.query_one("#event-counts", Static).render())


@pytest.mark.asyncio
async def test_pause_suppresses_appending():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        modal = DebugModal()
        await app.push_screen(modal)
        await pilot.pause(0.05)
        modal.paused = True
        # Buffer grows but rendering shouldn't change (rendering not deterministic).
        modal.push(parse_event(chunk()))
        modal.push(parse_event(chunk()))
        await pilot.pause(0.05)
        assert modal.paused is True
        assert len(modal._buffer) == 2


@pytest.mark.asyncio
async def test_clear_empties_buffer():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        modal = DebugModal([parse_event(chunk()) for _ in range(5)])
        await app.push_screen(modal)
        await pilot.pause(0.05)
        modal.action_clear()
        assert len(modal._buffer) == 0
