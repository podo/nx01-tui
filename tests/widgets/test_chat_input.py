"""ChatInput widget tests — ctrl+j submission."""

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
