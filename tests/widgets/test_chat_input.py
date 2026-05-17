"""ChatInput widget tests — Enter / Shift+Enter / Alt+Enter / ctrl+j."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from nx01_tui.tui.widgets import ChatInput


class _Host(App):
    received: list[str] = []

    def compose(self) -> ComposeResult:
        yield ChatInput()

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        self.received.append(event.text)


@pytest.mark.asyncio
async def test_ctrl_j_submits_and_clears():
    app = _Host()
    app.received = []
    async with app.run_test() as pilot:
        ci = app.query_one(ChatInput)
        ci.text = "hello world"
        ci.focus()
        await pilot.pause(0.05)
        await pilot.press("ctrl+j")
        await pilot.pause(0.05)
        assert app.received == ["hello world"]
        assert ci.text == ""


@pytest.mark.asyncio
async def test_empty_submit_is_noop():
    app = _Host()
    app.received = []
    async with app.run_test() as pilot:
        ci = app.query_one(ChatInput)
        ci.text = "   "
        ci.focus()
        await pilot.press("ctrl+j")
        await pilot.pause(0.05)
        assert app.received == []


@pytest.mark.asyncio
async def test_enter_submits_and_clears():
    app = _Host()
    app.received = []
    async with app.run_test() as pilot:
        ci = app.query_one(ChatInput)
        ci.text = "hi there"
        ci.focus()
        await pilot.pause(0.05)
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert app.received == ["hi there"]
        assert ci.text == ""


@pytest.mark.asyncio
async def test_shift_enter_inserts_newline_no_submit():
    app = _Host()
    app.received = []
    async with app.run_test() as pilot:
        ci = app.query_one(ChatInput)
        ci.text = "line one"
        # Cursor at end so insert appends.
        ci.cursor_location = ci.document.end
        ci.focus()
        await pilot.pause(0.05)
        await pilot.press("shift+enter")
        await pilot.pause(0.05)
        assert "\n" in ci.text
        assert app.received == []


@pytest.mark.asyncio
async def test_alt_enter_inserts_newline_no_submit():
    app = _Host()
    app.received = []
    async with app.run_test() as pilot:
        ci = app.query_one(ChatInput)
        ci.text = "line one"
        ci.cursor_location = ci.document.end
        ci.focus()
        await pilot.pause(0.05)
        await pilot.press("alt+enter")
        await pilot.pause(0.05)
        assert "\n" in ci.text
        assert app.received == []
