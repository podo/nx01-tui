"""User and Assistant message bubbles."""

from __future__ import annotations

from rich.markdown import Markdown as RichMarkdown

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

    During streaming a plain Static widget is used for fast text rendering
    (no Markdown parsing on every flush). On finalise() the Static is swapped
    out for a Textual Markdown widget (one-time parse). After the next user
    turn, freeze() further collapses the Markdown DOM to a single Rich-
    rendered Static to minimise live node count.

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
        self._stream_view: Static | None = None
        self._md: Markdown | None = None
        self._dirty: bool = bool(initial)
        self._flush_timer = None
        self._finalised: bool = False

    def compose(self) -> ComposeResult:
        yield Static("── assistant ──", classes="role-divider")
        self._stream_view = Static(self._buffer)
        yield self._stream_view
        self._md = Markdown(self._buffer)
        self._md.display = False
        yield self._md

    def on_mount(self) -> None:
        self._flush_timer = self.set_interval(0.05, self._flush)

    def _flush(self) -> None:
        if self._dirty and not self._finalised and self._stream_view is not None:
            self._stream_view.update(self._buffer)
            self._dirty = False

    def append(self, text: str) -> None:
        self._buffer += text
        self._dirty = True

    def finalise(self) -> None:
        if self._flush_timer is not None:
            self._flush_timer.stop()
            self._flush_timer = None
        self._finalised = True
        self._dirty = False
        if self._md is not None:
            self._md.update(self._buffer)
            self._md.display = True
        if self._stream_view is not None:
            self._stream_view.remove()
            self._stream_view = None

    def freeze(self) -> None:
        """Replace the live Markdown widget with a single Rich-rendered Static.

        Called by ConversationView when the next user message arrives.  Shrinks
        the Textual DOM by collapsing the many child nodes of the Markdown
        widget into a single opaque Static.
        """
        if self._md is None:
            return
        replacement = Static(RichMarkdown(self._buffer))
        self.mount(replacement, after=self._md)
        self._md.remove()
        self._md = None
