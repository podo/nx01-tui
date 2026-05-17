"""ThinkingBlock — collapsible yellow-bordered block streaming agent thoughts.

Behaviour:
  - Created when first AgentThinkingEvent arrives.
  - Streams chunks into a RichLog while .thinking is True.
  - On done(), records duration, collapses, and updates the header.
"""

from __future__ import annotations

import time

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import RichLog, Static

from .chevron import ExpandChevron
from .spinner import SpinnerWidget


class ThinkingBlock(Vertical):
    DEFAULT_CSS = """
    ThinkingBlock {
        border: round $warning;
        margin: 0 0 1 0;
        padding: 0 1;
        height: auto;
    }
    ThinkingBlock.done {
        border: round $warning 30%;
        opacity: 0.7;
    }
    ThinkingBlock #header {
        height: 1;
    }
    ThinkingBlock #header > ExpandChevron { width: 3; }
    ThinkingBlock #header > Static#label    { width: 1fr; color: $warning; }
    ThinkingBlock #header > Static#hint     { width: auto; color: $text-muted; }
    ThinkingBlock #header > SpinnerWidget   { width: 2; color: $warning; }
    ThinkingBlock RichLog {
        height: auto;
        max-height: 12;
        background: transparent;
        scrollbar-size: 1 1;
        color: $text-muted;
    }
    ThinkingBlock.collapsed RichLog { display: none; }
    """

    thinking: reactive[bool] = reactive(True)
    collapsed: reactive[bool] = reactive(False)

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._started_at = time.monotonic()
        self._duration_ms = 0
        self._timer = None
        self._log: RichLog | None = None

    def compose(self) -> ComposeResult:
        # While streaming, only the spinner is visible (single indicator —
        # #29 item 11). The chevron appears on done() when the block becomes
        # collapsible.
        with Horizontal(id="header", classes="thinking-header"):
            chev = ExpandChevron(expanded=True)
            chev.display = False  # hidden until done()
            yield chev
            yield SpinnerWidget("dots")
            yield Static("[bold]Thinking…[/]  [dim]0s[/]", id="label")
            yield Static("", id="hint")
        log = RichLog(highlight=False, markup=False, wrap=True)
        log.can_focus = False
        self._log = log
        yield log

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.1, self._tick_duration)

    def _tick_duration(self) -> None:
        if not self.thinking:
            return
        elapsed = int((time.monotonic() - self._started_at) * 1000)
        seconds = elapsed // 1000
        try:
            self.query_one("#label", Static).update(f"[bold]Thinking…[/]  [dim]{seconds}s[/]")
        except Exception:  # noqa: BLE001
            pass

    def append_chunk(self, text: str) -> None:
        if self._log is None:
            return
        # Strip trailing newline pieces — RichLog already line-breaks.
        for line in text.splitlines() or [text]:
            self._log.write(Text(line, style="dim"))

    def done(self) -> None:
        """Mark thinking complete; reveal chevron, collapse, record duration."""
        self.thinking = False
        self._duration_ms = int((time.monotonic() - self._started_at) * 1000)
        if self._timer is not None:
            self._timer.stop()
        # Single-indicator handoff: hide spinner, reveal chevron (#29 item 11).
        try:
            self.query_one(SpinnerWidget).display = False
        except Exception:  # noqa: BLE001
            pass
        try:
            self.query_one(ExpandChevron).display = True
        except Exception:  # noqa: BLE001
            pass
        seconds = self._duration_ms // 1000
        try:
            self.query_one("#label", Static).update(f"[dim]{seconds}s — thought[/]")
            self.query_one("#hint", Static).update("[dim]x to toggle[/]")
        except Exception:  # noqa: BLE001
            pass
        self.add_class("done")
        self.set_collapsed(True)

    # ── Collapse control ─────────────────────────────────────────────

    def set_collapsed(self, collapsed: bool) -> None:
        # While streaming, the block is always expanded (#29 item 11).
        if collapsed and self.thinking:
            return
        self.collapsed = collapsed
        if collapsed:
            self.add_class("collapsed")
        else:
            self.remove_class("collapsed")
        try:
            self.query_one(ExpandChevron).expanded = not collapsed
        except Exception:  # noqa: BLE001
            pass

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self.collapsed)

    # ── Keyboard / mouse ─────────────────────────────────────────────

    def on_click(self, event: events.Click) -> None:
        # Only toggle when the click originates in the #header subtree, so
        # text selection inside the RichLog body doesn't accidentally collapse.
        node = event.widget
        while node is not None and node is not self:
            if getattr(node, "id", None) == "header":
                self.toggle_collapsed()
                return
            node = node.parent
