"""SessionsModal, MemoryModal, HelpModal smoke tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from nx01_tui.tui.modals import (
    HelpModal,
    MemoryModal,
    SessionAction,
    SessionEntry,
    SessionsModal,
)


class _Host(App):
    last_result: object = None

    def compose(self) -> ComposeResult:
        yield Static("host")


def _sample_sessions() -> list[SessionEntry]:
    return [
        SessionEntry(
            session_id="abc123",
            flavor="assistant",
            title="Deploy CI",
            last_active="2m ago",
            message_count=14,
            preview="how do I deploy",
        ),
        SessionEntry(
            session_id="def456",
            flavor="operator",
            title="Restart server",
            last_active="1h ago",
            message_count=3,
            preview="please restart",
        ),
    ]


@pytest.mark.asyncio
async def test_sessions_modal_renders_grouped_list():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        modal = SessionsModal(_sample_sessions())
        await app.push_screen(modal)
        await pilot.pause(0.1)
        from textual.widgets import OptionList

        lst = modal.query_one("#session-list", OptionList)
        # Includes flavor headers + 2 sessions = >=4 options
        assert lst.option_count >= 4


@pytest.mark.asyncio
async def test_sessions_modal_resume_action_dismisses_with_resume():
    """Action invoked directly — kbd dispatch is blocked by the filter Input."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        app.last_result = None

        def cb(r: object) -> None:
            app.last_result = r

        modal = SessionsModal(_sample_sessions())
        await app.push_screen(modal, cb)
        await pilot.pause(0.1)
        from textual.widgets import OptionList

        lst = modal.query_one("#session-list", OptionList)
        lst.highlighted = 1  # Skip the flavor header at index 0.
        modal.action_resume()
        await pilot.pause(0.05)
        assert isinstance(app.last_result, SessionAction)
        assert app.last_result.action == "resume"


@pytest.mark.asyncio
async def test_sessions_modal_new_session_action():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        app.last_result = None

        def cb(r: object) -> None:
            app.last_result = r

        modal = SessionsModal(_sample_sessions())
        await app.push_screen(modal, cb)
        await pilot.pause(0.05)
        modal.action_new_session()
        await pilot.pause(0.05)
        assert isinstance(app.last_result, SessionAction)
        assert app.last_result.action == "new"


@pytest.mark.asyncio
async def test_memory_modal_renders_both_tabs():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        modal = MemoryModal(
            agent_entries=["uv for packages", "Python 3.11+"],
            user_entries=["prefers green tea"],
        )
        await app.push_screen(modal)
        await pilot.pause(0.1)
        from textual.widgets import TabPane

        panes = modal.query(TabPane)
        assert len(panes) == 2


@pytest.mark.asyncio
async def test_help_modal_renders_keybinding_table():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        modal = HelpModal()
        await app.push_screen(modal)
        await pilot.pause(0.1)
        from textual.widgets import DataTable

        table = modal.query_one(DataTable)
        assert table.row_count > 10
