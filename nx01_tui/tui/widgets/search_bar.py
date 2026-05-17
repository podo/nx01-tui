"""SearchBar — floating search input above the ConversationView.

Shown on `ctrl+f`. Emits `SearchQuery` messages as the user types and
on Enter/n/N. ESC dismisses.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Input


class SearchBar(Input):
    DEFAULT_CSS = """
    SearchBar {
        display: none;
        dock: top;
        height: 3;
        border: round $primary;
        background: $surface;
    }
    SearchBar.visible { display: block; }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Dismiss", show=False),
        # Enter → next, Shift+Enter → prev (#29 item 9). Avoids collision
        # with the app's ctrl+n / ctrl+p bindings.
        Binding("enter", "next_match", "Next", show=False),
        Binding("shift+enter", "prev_match", "Prev", show=False),
    ]

    class Query(Message):
        def __init__(self, query: str, direction: int = 1) -> None:
            super().__init__()
            self.query = query
            self.direction = direction

    class Dismiss(Message):
        pass

    def __init__(self, **kwargs: object) -> None:
        super().__init__(placeholder="Search…", **kwargs)

    def show(self) -> None:
        self.add_class("visible")
        self.focus()

    def hide(self) -> None:
        self.remove_class("visible")

    def action_dismiss(self) -> None:
        self.value = ""
        self.hide()
        self.post_message(self.Dismiss())

    def action_next_match(self) -> None:
        self.post_message(self.Query(self.value, direction=1))

    def action_prev_match(self) -> None:
        self.post_message(self.Query(self.value, direction=-1))

    def on_input_changed(self, event: Input.Changed) -> None:
        self.post_message(self.Query(event.value, direction=1))
