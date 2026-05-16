"""PermissionModal — y/n/a key paths."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from nx01_tui.tui.modals import PermissionModal


class _Host(App):
    last_result: object = None

    def compose(self) -> ComposeResult:
        yield Static("host")


@pytest.mark.asyncio
async def test_y_returns_allow():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        app.last_result = None

        def cb(r: object) -> None:
            app.last_result = r

        await app.push_screen(PermissionModal(tool="bash", args="rm -rf .", risk="high"), cb)
        await pilot.pause(0.05)
        await pilot.press("y")
        await pilot.pause(0.05)
        assert app.last_result == "allow"


@pytest.mark.asyncio
async def test_n_returns_deny():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        app.last_result = None

        def cb(r: object) -> None:
            app.last_result = r

        await app.push_screen(PermissionModal(tool="bash", args="ls", risk="low"), cb)
        await pilot.pause(0.05)
        await pilot.press("n")
        await pilot.pause(0.05)
        assert app.last_result == "deny"


@pytest.mark.asyncio
async def test_a_returns_always_allow():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        app.last_result = None

        def cb(r: object) -> None:
            app.last_result = r

        await app.push_screen(PermissionModal(tool="bash", args="ls", risk="low"), cb)
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.pause(0.05)
        assert app.last_result == "always_allow"


@pytest.mark.asyncio
async def test_escape_returns_deny():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        app.last_result = None

        def cb(r: object) -> None:
            app.last_result = r

        await app.push_screen(PermissionModal(tool="bash", args="ls", risk="low"), cb)
        await pilot.pause(0.05)
        await pilot.press("escape")
        await pilot.pause(0.05)
        assert app.last_result == "deny"
