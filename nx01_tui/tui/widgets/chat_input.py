"""ChatInput — multi-line TextArea with ctrl+j submit, auto-expand height."""

from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea


class ChatInput(TextArea):
    """TextArea subclass that auto-expands and emits Submitted on ctrl+j.

    Shift+Enter inserts a newline (TextArea default behaviour on
    terminals supporting the Kitty keyboard protocol).
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
        Binding("ctrl+j", "submit", "Send", show=False),
    ]

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self, **kwargs: object) -> None:
        super().__init__(language=None, show_line_numbers=False, **kwargs)

    def action_submit(self) -> None:
        text = self.text.strip()
        if not text:
            return
        self.post_message(self.Submitted(text))
        self.clear()
