"""Modal list-focus tests (W4 + W6, podo/nx01-tui#26 D1 + #29 item 14).

CommandModal: list-focused, NO filter input at all (#29 item 14 removed it).
SessionsModal: list-focused, filter hidden behind `/`.
"""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Input, OptionList

from nx01_tui.tui.modals.command_modal import CommandModal
from nx01_tui.tui.modals.sessions_modal import SessionEntry, SessionsModal


class _CmdHost(App):
    selected: str | None = None

    def on_mount(self) -> None:
        def _capture(value):
            self.selected = value

        self.push_screen(CommandModal(), _capture)


class _SessionsHost(App):
    result = None

    def on_mount(self) -> None:
        def _capture(value):
            self.result = value

        sessions = [
            SessionEntry(session_id="s1", flavor="assistant", title="First"),
            SessionEntry(session_id="s2", flavor="assistant", title="Second"),
        ]
        self.push_screen(SessionsModal(sessions), _capture)


@pytest.mark.asyncio
async def test_command_modal_focuses_list_no_filter():
    """#29 item 14 — filter Input removed entirely; list has focus on open."""
    app = _CmdHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        modal = app.screen
        assert isinstance(modal, CommandModal)
        lst = modal.query_one("#cmd-list", OptionList)
        assert lst.has_focus
        # No filter Input should exist in the DOM.
        assert not modal.query(Input)


@pytest.mark.asyncio
async def test_command_modal_has_no_v2_rows():
    """#29 item 14 — V2-marked entries are hidden."""
    app = _CmdHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        modal = app.screen
        lst = modal.query_one("#cmd-list", OptionList)
        ids = [
            lst.get_option_at_index(i).id
            for i in range(lst.option_count)
            if lst.get_option_at_index(i).id
        ]
        # No v2_* action ids should be visible.
        assert not any(opt and opt.startswith("v2_") for opt in ids)


@pytest.mark.asyncio
async def test_command_modal_enter_selects():
    app = _CmdHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        modal = app.screen
        # Move past the disabled group header by pressing down once or twice.
        lst = modal.query_one("#cmd-list", OptionList)
        # Highlight the first enabled option.
        idx = next(
            i
            for i in range(lst.option_count)
            if (opt := lst.get_option_at_index(i)) and not opt.disabled and opt.id
        )
        lst.highlighted = idx
        expected = lst.get_option_at_index(idx).id
        await pilot.pause(0.05)
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert app.selected == expected


@pytest.mark.asyncio
async def test_sessions_modal_focuses_list_not_filter():
    app = _SessionsHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        modal = app.screen
        assert isinstance(modal, SessionsModal)
        lst = modal.query_one("#session-list", OptionList)
        inp = modal.query_one("#filter", Input)
        assert lst.has_focus
        assert not inp.has_focus
        assert not inp.has_class("visible")


@pytest.mark.asyncio
async def test_sessions_modal_slash_reveals_filter():
    app = _SessionsHost()
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        modal = app.screen
        await pilot.press("slash")
        await pilot.pause(0.1)
        inp = modal.query_one("#filter", Input)
        assert inp.has_class("visible")
        assert inp.has_focus
