"""AppHeader — top docked status bar: NX01 ⬤ domain · model · shortcuts."""

from __future__ import annotations

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
    model: reactive[str] = reactive("—")
    connected: reactive[bool] = reactive(False)

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

    def _brand_text(self) -> str:
        dot = "[$success]⬤[/]" if self.connected else "[$error]⬤[/]"
        return f"[bold]NX01[/bold]  {dot}  [cyan]{self.domain}[/]  [dim]·[/]  [dim]{self.model}[/]"

    def _hints_text(self) -> str:
        return "[dim]ctrl+p cmd · ctrl+s sessions · ctrl+m memory · ? help[/]"

    def _refresh_brand(self) -> None:
        try:
            self.query_one("#brand", Static).update(self._brand_text())
        except Exception:  # noqa: BLE001 — pre-mount safety
            pass
