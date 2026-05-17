"""ChatInput — multi-line TextArea: Enter sends, Shift/Alt+Enter newline."""

from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea


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
        Binding("enter", "submit", "Send", show=False, priority=True),
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

    def _on_text_area_changed(self, _event: TextArea.Changed) -> None:
        self.post_message(self.TextChanged(self.text))
