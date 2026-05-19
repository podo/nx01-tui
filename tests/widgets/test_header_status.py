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
async def test_header_has_no_status_dot():
    """Header brand text must not contain a status glyph — state is conveyed
    by text color + suffix only."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        hdr = app.query_one(AppHeader)
        for connected, reconnecting, auth_failed in (
            (True, False, False),
            (False, True, False),
            (False, False, True),
            (False, False, False),
        ):
            hdr.connected = connected
            hdr.reconnecting = reconnecting
            hdr.auth_failed = auth_failed
            await pilot.pause(0.05)
            text = hdr._brand_text()
            for glyph in ("⬤", "●", "•", "⠋"):
                assert glyph not in text, f"unexpected status glyph {glyph!r} found in {text!r}"


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


def test_pick_first_model_finds_string_model():
    from nx01_tui.tui.app import Nx01App

    snapshot = {"assistant": {"status": "running", "model": "claude-opus-4-5"}}
    assert Nx01App._pick_first_model(snapshot) == "claude-opus-4-5"


def test_pick_first_model_skips_non_string():
    from nx01_tui.tui.app import Nx01App

    # model as a dict (wrong format) should be skipped
    snapshot = {"assistant": {"status": "running", "model": {"default": "opus"}}}
    assert Nx01App._pick_first_model(snapshot) == ""


def test_flavor_state_has_model_field():
    from nx01_tui.tui.state import FlavorState

    s = FlavorState(name="assistant", model="claude-opus-4-5")
    assert s.model == "claude-opus-4-5"


def test_flavor_state_model_defaults_empty():
    from nx01_tui.tui.state import FlavorState

    s = FlavorState(name="assistant")
    assert s.model == ""
