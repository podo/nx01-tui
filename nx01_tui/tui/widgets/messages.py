"""User and Assistant message bubbles."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Markdown, Static


class UserMessage(Static):
    """User turn — softened in QA pass: no border rail, padding instead.

    Earlier the `tall $primary` border still rendered as a `▊` block. The
    QA recommendation (#29 item 7b further soften) drops the border and
    relies on background-boost + label + indent to mark the turn.
    """

    DEFAULT_CSS = """
    UserMessage {
        margin: 0 8 1 0;
        padding: 0 2;
        background: $boost;
        color: $text-muted;
    }
    """

    def __init__(self, text: str, **kwargs: object) -> None:
        super().__init__(f"[dim]── you ──[/]\n{text}", **kwargs)


class AssistantMessage(Vertical):
    """Streaming assistant turn — Static role-divider above a Markdown body.

    Earlier this extended `Markdown` directly and prepended a Rich-tag
    role-label to the markdown source; that leaked as literal text (QA
    item 24). Now the divider is a Static (Rich-aware) and the Markdown
    widget carries only the streamed body.
    """

    DEFAULT_CSS = """
    AssistantMessage {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
    }
    AssistantMessage > .role-divider {
        color: $primary;
        text-style: bold;
        margin-bottom: 0;
    }
    """

    def __init__(self, initial: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._buffer = initial
        self._md: Markdown | None = None

    def compose(self) -> ComposeResult:
        yield Static("── assistant ──", classes="role-divider")
        self._md = Markdown(self._buffer)
        yield self._md

    def append(self, text: str) -> None:
        self._buffer += text
        if self._md is not None:
            self._md.update(self._buffer)

    def finalise(self) -> None:
        # Buffer is the source of truth — no extra re-render needed since
        # `append` already pushed every chunk.
        return
