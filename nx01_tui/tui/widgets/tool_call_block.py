"""ToolCallBlock — inline collapsible block per tool call.

States: queued → active (green pulse) → done (collapsed) | error (red).
Renders diffs inline via rich.Text colored lines when tool emits diff output.
"""

from __future__ import annotations

import difflib
import time

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import RichLog, Static

from ..state import ToolStatus
from .chevron import ExpandChevron
from .spinner import StarSpinner

_STATUS_DISPLAY: dict[ToolStatus, tuple[str, str]] = {
    ToolStatus.QUEUED: ("○", "$text-muted"),
    ToolStatus.ACTIVE: ("", "$success"),  # spinner replaces icon
    ToolStatus.DONE: ("✓", "$success"),
    ToolStatus.ERROR: ("✗", "$error"),
}


class ToolCallBlock(Vertical):
    DEFAULT_CSS = """
    ToolCallBlock {
        border: round $panel;
        margin: 0 0 1 0;
        padding: 0 1;
        height: auto;
    }
    ToolCallBlock.queued  { opacity: 0.45; }
    ToolCallBlock.active  { border: round $success; }
    ToolCallBlock.done    { border: round $success 30%; opacity: 0.7; }
    ToolCallBlock.error   { border: round $error; }

    ToolCallBlock #header { height: 1; }
    ToolCallBlock #header > ExpandChevron { width: 3; }
    ToolCallBlock #header > StarSpinner    { width: 2; }
    ToolCallBlock #header > Static#icon    { width: 2; content-align: center middle; }
    ToolCallBlock #header > Static#name    { width: auto; }
    ToolCallBlock #header > Static#args    { width: 1fr; color: $text-muted; }
    ToolCallBlock #header > Static#elapsed { width: auto; color: $text-muted; }

    ToolCallBlock RichLog {
        height: auto;
        max-height: 20;
        background: transparent;
        color: $text-muted;
        scrollbar-size: 1 1;
    }
    ToolCallBlock.collapsed RichLog { display: none; }
    """

    status: reactive[ToolStatus] = reactive(ToolStatus.QUEUED)
    collapsed: reactive[bool] = reactive(False)

    def __init__(self, tool: str, args: str = "", call_id: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.tool = tool
        self.args = args
        self.call_id = call_id
        self._started_at = time.monotonic()
        self._elapsed_ms = 0
        self._timer = None
        self._log: RichLog | None = None
        self.add_class("queued")

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield ExpandChevron(expanded=False)
            yield StarSpinner()  # hidden when status != active
            yield Static("○", id="icon")
            yield Static(f"[bold]{self.tool}[/]", id="name")
            yield Static(f"[dim] {self.args}[/]" if self.args else "", id="args")
            yield Static("", id="elapsed")
        log = RichLog(highlight=False, markup=False, wrap=True)
        log.can_focus = False
        self._log = log
        yield log

    def on_mount(self) -> None:
        self._refresh_status_display()
        self._timer = self.set_interval(0.2, self._tick)

    def _tick(self) -> None:
        if self.status not in (ToolStatus.ACTIVE,):
            return
        elapsed = (time.monotonic() - self._started_at) * 1000
        try:
            self.query_one("#elapsed", Static).update(f"[dim]{elapsed / 1000:.1f}s[/]")
        except Exception:  # noqa: BLE001
            pass

    # ── State transitions ────────────────────────────────────────────

    def set_status(self, status: ToolStatus) -> None:
        self.status = status

    def watch_status(self, new: ToolStatus) -> None:
        # Flip CSS state class
        for cls in ("queued", "active", "done", "error"):
            self.remove_class(cls)
        self.add_class(new.value)
        # Auto-collapse on done, expand on active/error
        if new == ToolStatus.DONE:
            self.set_collapsed(True)
            self._elapsed_ms = int((time.monotonic() - self._started_at) * 1000)
            if self._timer is not None:
                self._timer.stop()
        elif new == ToolStatus.ERROR:
            self.set_collapsed(False)
            self._elapsed_ms = int((time.monotonic() - self._started_at) * 1000)
            if self._timer is not None:
                self._timer.stop()
        elif new == ToolStatus.ACTIVE:
            self.set_collapsed(False)
            self._started_at = time.monotonic()
        self._refresh_status_display()

    def _refresh_status_display(self) -> None:
        icon, _color = _STATUS_DISPLAY[self.status]
        try:
            self.query_one(StarSpinner).display = self.status == ToolStatus.ACTIVE
            icon_w = self.query_one("#icon", Static)
            icon_w.display = self.status != ToolStatus.ACTIVE
            icon_w.update(icon)
            if self.status in (ToolStatus.DONE, ToolStatus.ERROR):
                self.query_one("#elapsed", Static).update(f"[dim]{self._elapsed_ms / 1000:.1f}s[/]")
        except Exception:  # noqa: BLE001
            pass

    # ── Content ──────────────────────────────────────────────────────

    def append_output(self, text: str) -> None:
        if self._log is None:
            return
        for line in text.splitlines() or [text]:
            self._log.write(Text(line))

    def append_diff(self, old: str, new: str, filename: str = "") -> None:
        """Write a colored unified diff into the output log."""
        if self._log is None:
            return
        diff_lines = list(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{filename}" if filename else "old",
                tofile=f"b/{filename}" if filename else "new",
                n=3,
            )
        )
        for raw in diff_lines[:20]:
            line = raw.rstrip("\n")
            if line.startswith("+") and not line.startswith("+++"):
                self._log.write(Text(line, style="green"))
            elif line.startswith("-") and not line.startswith("---"):
                self._log.write(Text(line, style="red"))
            elif line.startswith("@@"):
                self._log.write(Text(line, style="cyan"))
            else:
                self._log.write(Text(line, style="dim"))
        extra = max(0, len(diff_lines) - 20)
        if extra:
            self._log.write(Text(f"… {extra} more lines", style="dim italic"))

    # ── Collapse control ─────────────────────────────────────────────

    def set_collapsed(self, collapsed: bool) -> None:
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

    def on_click(self, event: events.Click) -> None:
        # Header subtree only — keep RichLog body click-inert for text selection.
        node = event.widget
        while node is not None and node is not self:
            if getattr(node, "id", None) == "header":
                self.toggle_collapsed()
                return
            node = node.parent
