"""ConfirmModal — y/n keys and button clicks dismiss with the right value."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from nx01_tui.tui.modals import ConfirmModal


class _Host(App):
    last_result: object = None

    def compose(self) -> ComposeResult:
        yield Static("host")


@pytest.mark.asyncio
async def test_y_key_returns_true():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        app.last_result = None

        def cb(result: object) -> None:
            app.last_result = result

        await app.push_screen(ConfirmModal("Delete?", dangerous=True), cb)
        await pilot.pause(0.05)
        await pilot.press("y")
        await pilot.pause(0.05)
        assert app.last_result is True


@pytest.mark.asyncio
async def test_n_key_returns_false():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        app.last_result = None

        def cb(result: object) -> None:
            app.last_result = result

        await app.push_screen(ConfirmModal("Drop table?"), cb)
        await pilot.pause(0.05)
        await pilot.press("n")
        await pilot.pause(0.05)
        assert app.last_result is False
