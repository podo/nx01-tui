"""ChatInput → visible dropdown delegation (arrows, Enter, Tab, Escape).

When a sibling SlashDropdown / FilePickerDropdown has the `.visible`
class, the ChatInput priority bindings hand off these keys to the
dropdown so the user can navigate + complete without leaving the input.
Otherwise the keys fall through to normal TextArea behavior (or submit).
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.containers import Vertical

from nx01_tui.tui.widgets import ChatInput, FilePickerDropdown, SlashDropdown


class _Host(App):
    """Mirrors FlavorPane's input column: dropdowns above a ChatInput."""

    received: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield SlashDropdown(id="slash")
            yield FilePickerDropdown(id="files")
            yield ChatInput(id="input")

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        self.received.append(event.text)


@pytest.mark.asyncio
async def test_arrows_route_to_visible_slash_dropdown():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        slash = app.query_one(SlashDropdown)
        ci = app.query_one(ChatInput)
        ci.focus()
        # Show dropdown
        slash.update_for_text("/")
        await pilot.pause(0.05)
        assert slash.has_class("visible")
        first = slash.highlighted
        await pilot.press("down")
        await pilot.pause(0.05)
        assert slash.highlighted != first


@pytest.mark.asyncio
async def test_enter_completes_visible_slash_dropdown_and_does_not_submit():
    app = _Host()
    app.received = []
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        slash = app.query_one(SlashDropdown)
        ci = app.query_one(ChatInput)
        ci.text = "/help"
        ci.focus()
        slash.update_for_text("/help")
        await pilot.pause(0.05)
        assert slash.has_class("visible")
        await pilot.press("enter")
        await pilot.pause(0.1)
        # Dropdown hides on completion …
        assert not slash.has_class("visible")
        # … and Enter must not have triggered ChatInput.Submitted.
        assert app.received == []


@pytest.mark.asyncio
async def test_tab_completes_visible_slash_dropdown():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        slash = app.query_one(SlashDropdown)
        ci = app.query_one(ChatInput)
        ci.text = "/help"
        ci.focus()
        slash.update_for_text("/help")
        await pilot.pause(0.05)
        assert slash.has_class("visible")
        await pilot.press("tab")
        await pilot.pause(0.1)
        assert not slash.has_class("visible")


@pytest.mark.asyncio
async def test_escape_dismisses_visible_slash_dropdown():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        slash = app.query_one(SlashDropdown)
        ci = app.query_one(ChatInput)
        ci.focus()
        slash.update_for_text("/")
        await pilot.pause(0.05)
        assert slash.has_class("visible")
        await pilot.press("escape")
        await pilot.pause(0.05)
        assert not slash.has_class("visible")


@pytest.mark.asyncio
async def test_enter_submits_when_no_dropdown_visible():
    app = _Host()
    app.received = []
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        ci = app.query_one(ChatInput)
        ci.text = "hello"
        ci.focus()
        await pilot.pause(0.05)
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert app.received == ["hello"]


@pytest.mark.asyncio
async def test_arrow_keys_move_cursor_when_no_dropdown():
    """With no dropdown visible, arrows should move the cursor in TextArea."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        ci = app.query_one(ChatInput)
        ci.text = "line one\nline two"
        ci.cursor_location = ci.document.end
        ci.focus()
        await pilot.pause(0.05)
        loc_before = ci.cursor_location
        await pilot.press("up")
        await pilot.pause(0.05)
        # Cursor moved (or stayed if already at top — but we set it at end of
        # line two so up should bring it to line one).
        assert ci.cursor_location != loc_before
