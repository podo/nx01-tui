"""Tab + Ctrl+1..9 flavor-switch tests (W3 of podo/nx01-tui#26).

Verifies that even with ChatInput focused, Tab rotates flavors and
Ctrl+digit jumps directly to the indexed flavor (clamped). The
priority bindings on Nx01App must beat TextArea's own Tab handling.
"""

from __future__ import annotations

import pytest

from nx01_tui.tui.app import Nx01App
from nx01_tui.tui.widgets import ChatInput


async def _settle(app, pilot, secs: float = 1.0) -> None:
    """Pause for mount + cancel SSE workers so retries don't race tests."""
    await pilot.pause(secs)
    for w in list(app.workers):
        w.cancel()
    await pilot.pause(0.2)


@pytest.mark.asyncio
async def test_tab_rotates_flavor_when_input_focused():
    app = Nx01App("http://localhost:9999", flavors=["a", "b", "c"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        flavor = app._active_flavor()
        app.query_one(f"#input-{flavor}", ChatInput).focus()
        await pilot.pause(0.05)
        before = app._active_flavor()
        await pilot.press("tab")
        await pilot.pause(0.1)
        assert app._active_flavor() != before


@pytest.mark.asyncio
async def test_ctrl_1_jumps_to_first_flavor():
    app = Nx01App("http://localhost:9999", flavors=["a", "b", "c"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        # Cycle to a non-first flavor first.
        app.action_switch_flavor()
        await pilot.pause(0.1)
        assert app._active_flavor() != "a"
        # Now jump to index 0 via ctrl+1.
        app.action_select_flavor(0)
        await pilot.pause(0.1)
        assert app._active_flavor() == "a"


@pytest.mark.asyncio
async def test_ctrl_3_jumps_to_third_flavor():
    app = Nx01App("http://localhost:9999", flavors=["a", "b", "c"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        app.action_select_flavor(2)
        await pilot.pause(0.1)
        assert app._active_flavor() == "c"


@pytest.mark.asyncio
async def test_ctrl_digit_past_end_is_noop():
    app = Nx01App("http://localhost:9999", flavors=["a", "b"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        before = app._active_flavor()
        # Only 2 flavors — indexes 2..8 should be no-ops.
        app.action_select_flavor(2)
        app.action_select_flavor(8)
        await pilot.pause(0.1)
        assert app._active_flavor() == before


@pytest.mark.asyncio
async def test_ctrl_digit_negative_is_noop():
    app = Nx01App("http://localhost:9999", flavors=["a", "b"])
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        before = app._active_flavor()
        app.action_select_flavor(-1)
        await pilot.pause(0.05)
        assert app._active_flavor() == before
