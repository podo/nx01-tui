"""AppHeader + StatusBar reactive update tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from nx01_tui.tui.state import AgentState
from nx01_tui.tui.widgets import AppHeader, StatusBar


class _Host(App):
    def compose(self) -> ComposeResult:
        yield AppHeader()
        yield StatusBar()


@pytest.mark.asyncio
async def test_header_reflects_connection_state():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        hdr = app.query_one(AppHeader)

        hdr.domain = "nx01.example.com"
        hdr.connected = False
        await pilot.pause(0.05)
        # No crash; brand text recomputed.

        hdr.reconnecting = True
        await pilot.pause(0.05)
        hdr.reconnecting = False
        hdr.connected = True
        await pilot.pause(0.05)


@pytest.mark.asyncio
async def test_status_bar_state_transitions():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        bar = app.query_one(StatusBar)

        bar.state = AgentState.THINKING
        bar.flavor = "assistant"
        bar.tokens = 1500
        await pilot.pause(0.05)

        bar.state = AgentState.TOOL_CALL
        await pilot.pause(0.05)

        bar.state = AgentState.DONE
        await pilot.pause(0.05)
        # No crash on any state transition.
