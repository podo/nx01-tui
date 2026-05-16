"""SlashDropdown widget tests — show/hide on / prefix, fuzzy filter."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from nx01_tui.tui.widgets import SlashDropdown


class _Host(App):
    def compose(self) -> ComposeResult:
        yield SlashDropdown()


@pytest.mark.asyncio
async def test_hidden_when_text_does_not_start_with_slash():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(SlashDropdown)
        dd.update_for_text("hello")
        assert not dd.has_class("visible")


@pytest.mark.asyncio
async def test_visible_with_slash_prefix():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(SlashDropdown)
        dd.update_for_text("/")
        assert dd.has_class("visible")
        assert dd.option_count > 0


@pytest.mark.asyncio
async def test_fuzzy_filter_narrows_options():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(SlashDropdown)
        dd.update_for_text("/")
        full = dd.option_count
        dd.update_for_text("/mem")
        narrowed = dd.option_count
        assert 0 < narrowed < full


@pytest.mark.asyncio
async def test_no_matches_hides_dropdown():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(SlashDropdown)
        dd.update_for_text("/xyzdoesnotexist")
        assert not dd.has_class("visible")
