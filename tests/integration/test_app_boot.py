"""Headless smoke tests for the main Nx01App boot path."""

from __future__ import annotations

import pytest

from nx01_tui.tui.app import Nx01App
from nx01_tui.tui.events import parse_event
from nx01_tui.tui.widgets import AppHeader, FlavorPane
from tests.fixtures.sample_events import chunk, thinking, tool_started, turn_done


@pytest.mark.asyncio
async def test_app_boots_with_initial_flavors():
    app = Nx01App("http://localhost:9999", api_key=None, flavors=["assistant", "operator"])
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        assert set(app._states.keys()) == {"assistant", "operator"}
        # Both panes mounted
        assert len(app.query(FlavorPane)) == 2


@pytest.mark.asyncio
async def test_header_shows_domain():
    app = Nx01App("http://nx01.example.com", api_key=None, flavors=["assistant"])
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        header = app.query_one(AppHeader)
        assert header.domain == "nx01.example.com"


@pytest.mark.asyncio
async def test_event_dispatch_drives_pane_state():
    app = Nx01App("http://localhost:9999", api_key=None, flavors=["assistant"])
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        # Drive a full turn through the dispatcher.
        app._dispatch_event(parse_event(thinking()))
        await pilot.pause(0.1)
        pane = app._panes["assistant"]
        assert pane.has_class("thinking")

        app._dispatch_event(parse_event(chunk(text="answer")))
        await pilot.pause(0.1)
        assert pane.has_class("streaming")

        app._dispatch_event(parse_event(tool_started()))
        await pilot.pause(0.1)
        assert pane.has_class("tool_call")

        app._dispatch_event(parse_event(turn_done()))
        await pilot.pause(0.1)
        assert pane.has_class("done")


@pytest.mark.asyncio
async def test_help_modal_opens_and_closes():
    app = Nx01App("http://localhost:9999", api_key=None, flavors=["assistant"])
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        await pilot.press("question_mark")
        await pilot.pause(0.2)
        # HelpModal is on the screen stack
        assert app.screen_stack[-1].__class__.__name__ == "HelpModal"
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert app.screen_stack[-1].__class__.__name__ != "HelpModal"


@pytest.mark.asyncio
async def test_command_modal_opens():
    app = Nx01App("http://localhost:9999", api_key=None, flavors=["assistant"])
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        await pilot.press("ctrl+p")
        await pilot.pause(0.2)
        assert app.screen_stack[-1].__class__.__name__ == "CommandModal"


@pytest.mark.asyncio
async def test_extract_last_code_block():
    text = "intro\n```python\nprint('hi')\nprint('bye')\n```\noutro"
    code = Nx01App._extract_last_code_block(text)
    assert code == "print('hi')\nprint('bye')"


@pytest.mark.asyncio
async def test_yank_last_code_with_no_block_notifies():
    app = Nx01App("http://localhost:9999", api_key=None, flavors=["assistant"])
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        app._states["assistant"].messages.append({"type": "chunk", "text": "plain text only"})
        app.action_yank_last_code()  # should not raise
