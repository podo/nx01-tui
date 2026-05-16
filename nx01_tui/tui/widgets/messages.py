"""User and Assistant message bubbles."""

from __future__ import annotations

from textual.widgets import Markdown, Static


class UserMessage(Static):
    DEFAULT_CSS = """
    UserMessage {
        margin: 0 8 1 0;
        padding: 0 1;
        background: $boost;
        border-left: thick $primary;
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
        super().__init__(initial, **kwargs)
        self._buffer = initial

    def append(self, text: str) -> None:
        self._buffer += text
        self.update(self._buffer)

    def finalise(self) -> None:
        # Trigger one final re-render (no-op if Markdown is idempotent)
        self.update(self._buffer)
