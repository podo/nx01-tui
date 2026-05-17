"""ExpandChevron widget tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from nx01_tui.tui.widgets import ExpandChevron


class _Host(App):
    def compose(self) -> ComposeResult:
        yield ExpandChevron()


@pytest.mark.asyncio
async def test_chevron_starts_collapsed_arrow():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        ch = app.query_one(ExpandChevron)
        assert str(ch.render()) == "▶"
        assert ch.expanded is False


@pytest.mark.asyncio
async def test_chevron_toggle_flips_arrow():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        ch = app.query_one(ExpandChevron)
        ch.toggle()
        await pilot.pause(0.05)
        assert str(ch.render()) == "▼"
        assert ch.expanded is True
        ch.toggle()
        await pilot.pause(0.05)
        assert str(ch.render()) == "▶"
