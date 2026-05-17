"""User and Assistant message bubbles."""

from __future__ import annotations

from textual.widgets import Markdown, Static


class UserMessage(Static):
    DEFAULT_CSS = """
    UserMessage {
        margin: 0 8 1 0;
        padding: 0 1;
        background: $boost;
        border-left: tall $primary;
        color: $text-muted;
    }
    """

    def __init__(self, text: str, **kwargs: object) -> None:
        super().__init__(f"[dim]── you ──[/]\n{text}", **kwargs)


class AssistantMessage(Markdown):
    """Streaming markdown — updated via append()."""

    DEFAULT_CSS = """
    AssistantMessage {
        margin: 0 0 1 0;
        padding: 0 1;
    }
    """

    def __init__(self, initial: str = "", **kwargs: object) -> None:
        # Symmetry with UserMessage's role divider (#29 item 24).
        self._role_label = "[bold $primary]── assistant ──[/]\n"
        super().__init__(self._role_label + initial, **kwargs)
        self._buffer = initial

    def append(self, text: str) -> None:
        self._buffer += text
        self.update(self._role_label + self._buffer)

    def finalise(self) -> None:
        self.update(self._role_label + self._buffer)
