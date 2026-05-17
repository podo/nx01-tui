"""DebugModal — raw SSE event log with filter, pause, and copy.

Mounted on demand and fed live SseEvents from the App. Useful when
something looks wrong and you want to see exactly what the backend
emitted vs what the widgets rendered.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, is_dataclass
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Input, RichLog, Static

from ..events import SseEvent
from .base import BaseModal

_MAX_BUFFERED_EVENTS = 500


class DebugModal(BaseModal):
    DEFAULT_CSS = """
    DebugModal .dialog { width: 90%; height: 90%; }
    DebugModal #filter { height: 3; margin-bottom: 1; }
    DebugModal RichLog { height: 1fr; background: $background; border: round $panel; }
    DebugModal #event-counts { color: $text-muted; height: 1; }
    DebugModal #footer-row { height: 3; align-horizontal: right; }
    DebugModal #footer-row Button { margin-left: 1; }
    """

    BINDINGS = [
        Binding("p", "toggle_paused", "Pause/resume", show=True),
        Binding("ctrl+l", "clear", "Clear", show=True),
        Binding("ctrl+y", "yank_buffer", "Copy buffer", show=True),
    ]

    paused: reactive[bool] = reactive(False)
    filter_text: reactive[str] = reactive("")

    def __init__(self, initial_buffer: list[SseEvent] | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._buffer: deque[SseEvent] = deque(maxlen=_MAX_BUFFERED_EVENTS)
        if initial_buffer:
            self._buffer.extend(initial_buffer[-_MAX_BUFFERED_EVENTS:])

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Debug · raw SSE event log[/]", classes="dialog-title")
            yield Input(placeholder="Filter by event type…", id="filter")
            yield Static("0 events buffered · live", id="event-counts")
            yield RichLog(highlight=True, markup=False, wrap=False, id="event-log")
            # Footer row (#29 item 16) — actions right-aligned, separated from
            # the filter input so labels never crop.
            with Horizontal(id="footer-row"):
                yield Button("Pause (p)", id="pause-btn", variant="warning")
                yield Button("Clear (ctrl+l)", id="clear-btn")
                yield Button("Copy (ctrl+y)", id="copy-btn", variant="primary")

    def on_mount(self) -> None:
        self._render_buffer()

    # ── Public API ────────────────────────────────────────────────────

    def push(self, event: SseEvent) -> None:
        """Append an event; respects pause + filter."""
        self._buffer.append(event)
        if self.paused:
            return
        if not self._matches(event):
            return
        self._append_line(event)
        self._refresh_counts()

    # ── Filter + pause ────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        self.filter_text = event.value
        self._render_buffer()

    def watch_paused(self, _val: bool) -> None:
        try:
            btn = self.query_one("#pause-btn", Button)
        except Exception:  # noqa: BLE001
            return
        btn.label = "Resume (p)" if self.paused else "Pause (p)"
        self._refresh_counts()

    def action_toggle_paused(self) -> None:
        self.paused = not self.paused

    def action_clear(self) -> None:
        self._buffer.clear()
        self._render_buffer()

    def action_yank_buffer(self) -> None:
        text = "\n".join(self._format(e) for e in self._buffer)
        self.app.copy_to_clipboard(text)
        self.notify(f"Copied {len(self._buffer)} events ({len(text)} chars)")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pause-btn":
            self.action_toggle_paused()
        elif event.button.id == "clear-btn":
            self.action_clear()
        elif event.button.id == "copy-btn":
            self.action_yank_buffer()

    # ── Rendering ─────────────────────────────────────────────────────

    def _matches(self, event: SseEvent) -> bool:
        if not self.filter_text:
            return True
        needle = self.filter_text.lower()
        haystack = (event.type + " " + event.flavor).lower()
        return needle in haystack

    def _render_buffer(self) -> None:
        try:
            log = self.query_one("#event-log", RichLog)
        except Exception:  # noqa: BLE001
            return
        log.clear()
        for ev in self._buffer:
            if self._matches(ev):
                log.write(self._format(ev))
        self._refresh_counts()

    def _append_line(self, event: SseEvent) -> None:
        try:
            self.query_one("#event-log", RichLog).write(self._format(event))
        except Exception:  # noqa: BLE001
            pass

    def _format(self, event: SseEvent) -> str:
        payload: dict[str, Any] = {}
        if is_dataclass(event):
            payload = asdict(event)
        else:
            payload = getattr(event, "raw", {}) or {}
        # Compact one-liner: timestamp.flavor TYPE {payload (minus raw + type)}
        clone = {k: v for k, v in payload.items() if k not in ("raw", "type")}
        payload_str = json.dumps(clone, default=str)[:300]
        flavor = event.flavor or "-"
        return f"{event.at:.2f}  [{flavor:12}]  {event.type:30}  {payload_str}"

    def _refresh_counts(self) -> None:
        try:
            status = "paused" if self.paused else "live"
            self.query_one("#event-counts", Static).update(
                f"{len(self._buffer)} events buffered · {status}"
            )
        except Exception:  # noqa: BLE001
            pass
