"""StatusBar — bottom bar showing agent state + active flavor (#29 item 1).

Replaces Textual's `Footer`. Sidebar already surfaces context-window size and
the help modal surfaces shortcuts, so this bar is intentionally minimal:
state on the left, flavor on the right.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static

from ..state import AgentState

_STATE_DISPLAY: dict[AgentState, tuple[str, str]] = {
    AgentState.IDLE: ("Ready", "dim"),
    AgentState.THINKING: ("Thinking…", "$warning"),
    AgentState.STREAMING: ("Writing…", "$primary"),
    AgentState.TOOL_CALL: ("Tool call", "$success"),
    AgentState.DONE: ("Done", "$success"),
    AgentState.ERROR: ("Error", "$error"),
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
    StatusBar #spacer   { width: 1fr; }
    StatusBar #flavor   { width: auto; color: $text-muted; }
    """

    state: reactive[AgentState] = reactive(AgentState.IDLE)
    flavor: reactive[str] = reactive("")
    tokens: reactive[int] = reactive(0)
    token_limit: reactive[int] = reactive(200_000)

    def compose(self) -> ComposeResult:
        yield Static(self._state_text(), id="state")
        yield Static("", id="spacer")
        yield Static(self._flavor_text(), id="flavor")

    def watch_state(self, _new: AgentState) -> None:
        self._refresh_state()

    def watch_flavor(self, _new: str) -> None:
        self._refresh_flavor()

    def watch_tokens(self, _new: int) -> None:
        # Tokens still tracked for backward-compat; surfaced by the sidebar.
        pass

    def _state_text(self) -> str:
        label, color = _STATE_DISPLAY.get(self.state, _STATE_DISPLAY[AgentState.IDLE])
        return f"[{color}]{label}[/]"

    def _flavor_text(self) -> str:
        return f"[dim]{self.flavor}[/]" if self.flavor else ""

    def _refresh_state(self) -> None:
        try:
            self.query_one("#state", Static).update(self._state_text())
        except Exception:  # noqa: BLE001
            pass

    def _refresh_flavor(self) -> None:
        try:
            self.query_one("#flavor", Static).update(self._flavor_text())
        except Exception:  # noqa: BLE001
            pass
