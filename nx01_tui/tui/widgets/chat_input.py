"""ChatInput — multi-line TextArea: Enter sends, Shift/Alt+Enter newline.

When a sibling SlashDropdown / FilePickerDropdown is `.visible`, the
priority bindings here delegate arrow / Enter / Tab / Escape to the
dropdown so the user can navigate + complete entries without leaving
the input. See podo/nx01-tui#26 W10.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import OptionList, TextArea


class ChatInput(TextArea):
    """TextArea subclass that auto-expands and submits on Enter.

    - `enter`         → submit (chat-app convention)
    - `shift+enter`   → insert newline (Kitty/WezTerm/Ghostty/iTerm2 w/ modifier reporting)
    - `alt+enter`     → insert newline (fallback for Terminal.app where shift+enter == enter)
    - `ctrl+j`        → submit (universal terminal fallback)
    """

    DEFAULT_CSS = """
    ChatInput {
        height: auto;
        min-height: 2;
        max-height: 8;
        border: round $panel;
        background: $surface;
        padding: 0 1;
    }
    ChatInput:focus {
        border: round $primary;
    }
    """

    BINDINGS = [
        # Enter: complete a visible dropdown, otherwise submit.
        Binding("enter", "input_enter", "Send", show=False, priority=True),
        # Arrows: move dropdown highlight when visible, otherwise cursor.
        Binding("up", "input_up", show=False, priority=True),
        Binding("down", "input_down", show=False, priority=True),
        # Tab: complete dropdown if visible (no default ChatInput behavior).
        Binding("tab", "input_tab", show=False, priority=True),
        # Escape: dismiss dropdown if visible.
        Binding("escape", "input_escape", show=False, priority=True),
        Binding("shift+enter", "newline", "Newline", show=False, priority=True),
        Binding("alt+enter", "newline", "Newline", show=False, priority=True),
        Binding("ctrl+j", "submit", "Send", show=False),
    ]

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self, **kwargs: object) -> None:
        super().__init__(language=None, show_line_numbers=False, **kwargs)

    class TextChanged(Message):
        """Posted on every keystroke so a SlashDropdown sibling can react."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def action_submit(self) -> None:
        text = self.text.strip()
        if not text:
            return
        self.post_message(self.Submitted(text))
        self.clear()

    def action_newline(self) -> None:
        # Insert a literal newline at the cursor — used by shift+enter
        # and alt+enter so multi-line composition still works after we
        # took the bare `enter` for submit.
        self.insert("\n")

    # ── Dropdown delegation ─────────────────────────────────────────

    def _visible_dropdown(self) -> OptionList | None:
        """The visible sibling OptionList (slash / file picker), if any.

        We look up the FlavorPane subtree via the parent; dropdowns sit
        in the same Vertical container as this input.
        """
        if self.parent is None:
            return None
        try:
            for dd in self.parent.query(OptionList):
                if dd.has_class("visible"):
                    return dd
        except Exception:  # noqa: BLE001
            return None
        return None

    def action_input_enter(self) -> None:
        dd = self._visible_dropdown()
        if dd is not None and hasattr(dd, "action_complete"):
            dd.action_complete()
            return
        self.action_submit()

    def action_input_up(self) -> None:
        dd = self._visible_dropdown()
        if dd is not None:
            dd.action_cursor_up()
            return
        self.action_cursor_up()

    def action_input_down(self) -> None:
        dd = self._visible_dropdown()
        if dd is not None:
            dd.action_cursor_down()
            return
        self.action_cursor_down()

    def action_input_tab(self) -> None:
        dd = self._visible_dropdown()
        if dd is not None and hasattr(dd, "action_complete"):
            dd.action_complete()
        # No-op when no dropdown — Tab in ChatInput shouldn't insert a tab
        # char (we don't want indented prose) and shouldn't change focus
        # (the app-level Tab binding cycles flavor tabs instead).

    def action_input_escape(self) -> None:
        dd = self._visible_dropdown()
        if dd is not None and hasattr(dd, "action_dismiss"):
            dd.action_dismiss()
        # No fall-through: ESC inside ChatInput is dropdown-only. Modal
        # close uses the app/screen-level binding which won't reach here
        # because the modal screen owns its own focus.

    def _on_text_area_changed(self, _event: TextArea.Changed) -> None:
        self.post_message(self.TextChanged(self.text))
