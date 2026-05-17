"""AppHeader — top docked status bar: NX01 · domain · model · shortcuts.

Connection state is conveyed by the domain's text color + a parenthetical
suffix (auth failed / reconnecting / offline). No status dot.
"""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static


class AppHeader(Horizontal):
    """Single-line header docked at top of the app."""

    DEFAULT_CSS = """
    AppHeader {
        dock: top;
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    AppHeader #brand   { width: auto; color: $text; }
    AppHeader #spacer  { width: 1fr; }
    AppHeader #hints   { width: auto; color: $text-muted; }
    """

    domain: reactive[str] = reactive("disconnected")
    # Empty string means "no model yet"; the renderer shows a dim hint
    # instead of an em-dash (#29 item 18).
    model: reactive[str] = reactive("")
    connected: reactive[bool] = reactive(False)
    reconnecting: reactive[bool] = reactive(False)
    auth_failed: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        yield Static(self._brand_text(), id="brand")
        yield Static("", id="spacer")
        yield Static(self._hints_text(), id="hints")

    def watch_domain(self, _value: str) -> None:
        self._refresh_brand()

    def watch_model(self, _value: str) -> None:
        self._refresh_brand()

    def watch_connected(self, _value: bool) -> None:
        self._refresh_brand()

    def watch_reconnecting(self, _value: bool) -> None:
        self._refresh_brand()

    def watch_auth_failed(self, _value: bool) -> None:
        self._refresh_brand()

    def _brand_text(self) -> str:
        # Color-only state signalling (#29 item 19) — long detail moves to a
        # toast so the header stays tight even when something goes wrong.
        sep = "[dim]┃[/]"
        if self.auth_failed:
            domain = f"[$error]{self.domain}[/]  [bold $error]AUTH[/]"
        elif self.reconnecting:
            domain = f"[$warning]{self.domain}[/]  [dim]reconnecting[/]"
        elif self.connected:
            domain = f"[cyan]{self.domain}[/]"
        else:
            domain = f"[$error]{self.domain}[/]  [dim]offline[/]"
        # Model fallback (#29 item 18) — empty → dim italic hint.
        if self.model:
            model = f"[dim]{self._format_model(self.model)}[/]"
        else:
            model = "[dim italic]no model[/]"
        return f"[bold]NX01[/bold]  {sep}  {domain}  {sep}  {model}"

    @staticmethod
    def _format_model(model: str) -> str:
        """Compact display: claude-opus-4-5-20250514 → opus-4.5."""
        name = re.sub(r"^claude-", "", model)
        name = re.sub(r"-\d{8}$", "", name)
        name = re.sub(r"(\d+)-(\d+)$", r"\1.\2", name)
        return (name[:22] + "…") if len(name) > 22 else name

    def _hints_text(self) -> str:
        return "[dim]ctrl+p cmd · ctrl+s sessions · ctrl+m memory · ? help[/]"

    def _refresh_brand(self) -> None:
        try:
            self.query_one("#brand", Static).update(self._brand_text())
        except Exception:  # noqa: BLE001 — pre-mount safety
            pass
