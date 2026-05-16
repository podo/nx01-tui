"""StatusBar — bottom docked bar showing agent state, tokens, shortcuts."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static

from ..state import AgentState

_STATE_DISPLAY: dict[AgentState, tuple[str, str]] = {
    AgentState.IDLE: ("● Ready", "dim"),
    AgentState.THINKING: ("⠋ Thinking…", "$warning"),
    AgentState.STREAMING: ("▌ Writing…", "$primary"),
    AgentState.TOOL_CALL: ("✻ Tool call", "$success"),
    AgentState.DONE: ("✓ Done", "$success"),
    AgentState.ERROR: ("✗ Error", "$error"),
}


class StatusBar(Horizontal):
    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    StatusBar #state    { width: auto; }
    StatusBar #spacer-l { width: 1fr; }
    StatusBar #tokens   { width: auto; color: $text-muted; }
    StatusBar #spacer-r { width: 1fr; }
    StatusBar #shortcuts{ width: auto; color: $text-muted; }
    """

    state: reactive[AgentState] = reactive(AgentState.IDLE)
    flavor: reactive[str] = reactive("")
    tokens: reactive[int] = reactive(0)
    token_limit: reactive[int] = reactive(200_000)

    def compose(self) -> ComposeResult:
        yield Static(self._state_text(), id="state")
        yield Static("", id="spacer-l")
        yield Static(self._tokens_text(), id="tokens")
        yield Static("", id="spacer-r")
        yield Static("[dim]y copy · ctrl+f search · x expand[/]", id="shortcuts")

    def watch_state(self, _new: AgentState) -> None:
        self._refresh_state()

    def watch_flavor(self, _new: str) -> None:
        self._refresh_state()

    def watch_tokens(self, _new: int) -> None:
        self._refresh_tokens()

    def _state_text(self) -> str:
        label, color = _STATE_DISPLAY.get(self.state, _STATE_DISPLAY[AgentState.IDLE])
        flavor_part = f" [dim]· {self.flavor}[/]" if self.flavor else ""
        return f"[{color}]{label}[/]{flavor_part}"

    def _tokens_text(self) -> str:
        if not self.token_limit:
            return ""
        pct = (self.tokens / self.token_limit) * 100
        return f"[dim]{self.tokens:,} / {self.token_limit:,} · {pct:.0f}%[/]"

    def _refresh_state(self) -> None:
        try:
            self.query_one("#state", Static).update(self._state_text())
        except Exception:  # noqa: BLE001
            pass

    def _refresh_tokens(self) -> None:
        try:
            self.query_one("#tokens", Static).update(self._tokens_text())
        except Exception:  # noqa: BLE001
            pass
