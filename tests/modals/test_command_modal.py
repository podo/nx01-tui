"""CommandModal — fuzzy filter, navigation, dismiss tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button

from nx01_tui.tui.modals import CommandModal, default_commands


class _Host(App):
    def compose(self) -> ComposeResult:
        yield Button("trigger")

    async def open_command_modal(self) -> object:
        return await self.push_screen_wait(CommandModal(default_commands()))


@pytest.mark.asyncio
async def test_command_modal_renders_categorised_options():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        modal = CommandModal(default_commands())
        await app.push_screen(modal)
        await pilot.pause(0.1)
        # Has at least one option per category.
        from textual.widgets import OptionList

        lst = modal.query_one("#cmd-list", OptionList)
        assert lst.option_count > 5


@pytest.mark.asyncio
async def test_filter_narrows_visible_options():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        modal = CommandModal(default_commands())
        await app.push_screen(modal)
        await pilot.pause(0.05)
        from textual.widgets import Input, OptionList

        before = modal.query_one("#cmd-list", OptionList).option_count
        modal.query_one("#filter", Input).value = "memory"
        await pilot.pause(0.1)
        after = modal.query_one("#cmd-list", OptionList).option_count
        assert 0 < after < before


@pytest.mark.asyncio
async def test_escape_closes_modal():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await app.push_screen(CommandModal(default_commands()))
        await pilot.pause(0.05)
        assert app.screen.__class__.__name__ == "CommandModal"
        await pilot.press("escape")
        await pilot.pause(0.05)
        assert app.screen.__class__.__name__ != "CommandModal"
