"""MemoryModal — tabbed view of agent + user memory stores (read-only in V1)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, TabbedContent, TabPane

from .base import BaseModal


class MemoryModal(BaseModal):
    DEFAULT_CSS = """
    MemoryModal .dialog { width: 70; height: 80%; border: round $accent; }
    MemoryModal .memory-content {
        height: auto;
        background: $background;
        padding: 1;
        margin-top: 1;
    }
    """

    AGENT_LIMIT = 2200
    USER_LIMIT = 1375

    def __init__(self, agent_entries: list[str], user_entries: list[str], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.agent_entries = agent_entries
        self.user_entries = user_entries

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Memory[/]", classes="dialog-title")
            with TabbedContent():
                with TabPane("Agent Memory", id="tab-agent"):
                    yield from self._render_store(
                        self.agent_entries, self.AGENT_LIMIT, store="agent"
                    )
                with TabPane("User Profile", id="tab-user"):
                    yield from self._render_store(self.user_entries, self.USER_LIMIT, store="user")
            yield Static(
                "[dim]Read-only V1 — edit via /memory and /user commands · ESC close[/]",
                classes="dialog-hint",
            )

    def _render_store(self, entries: list[str], limit: int, store: str) -> ComposeResult:
        total_chars = sum(len(e) for e in entries)
        pct = (total_chars / limit) * 100 if limit else 0
        color = "$success" if pct < 75 else ("$warning" if pct < 90 else "$error")
        yield Static(
            f"[{color}]{total_chars:,} / {limit:,} chars  ({pct:.0f}%)[/]",
            classes="memory-content",
        )
        body = "\n\n".join(f"§ {e}" for e in entries) if entries else "[dim]empty[/]"
        yield Static(body, classes="memory-content")
