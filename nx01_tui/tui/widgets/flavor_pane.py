"""FlavorPane — horizontal container holding ConversationView + MonitorSidebar.

One per flavor tab. State class on the root drives border color transitions,
plus a top-of-pane ribbon (#29 item 21) that surfaces the current state in
words for a redundant cue independent of border colour.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from ..state import AgentState, FlavorState
from .chat_input import ChatInput
from .conversation import ConversationView
from .file_picker import FilePickerDropdown
from .search_bar import SearchBar
from .sidebar import MonitorSidebar
from .slash_dropdown import SlashDropdown

_STATE_RIBBON: dict[AgentState, tuple[str, str]] = {
    AgentState.THINKING: ("Thinking…", "$warning"),
    AgentState.STREAMING: ("Writing…", "$primary"),
    AgentState.TOOL_CALL: ("Tool call", "$success"),
    AgentState.ERROR: ("Error", "$error"),
}


class FlavorPane(Horizontal):
    """Composition root for one flavor's UI."""

    DEFAULT_CSS = """
    FlavorPane {
        layout: horizontal;
        height: 1fr;
        border: round $panel;
    }
    FlavorPane.thinking  { border: round $warning; }
    FlavorPane.streaming { border: round $primary; }
    FlavorPane.tool_call { border: round $success; }
    FlavorPane.done      { border: round $success 30%; }
    FlavorPane.error     { border: round $error; }
    FlavorPane .state-ribbon {
        display: none;
        height: 1;
        padding: 0 1;
        text-style: bold;
    }
    FlavorPane.thinking  .state-ribbon {
        display: block; background: $warning 20%; color: $warning;
    }
    FlavorPane.streaming .state-ribbon {
        display: block; background: $primary 20%; color: $primary;
    }
    FlavorPane.tool_call .state-ribbon {
        display: block; background: $success 20%; color: $success;
    }
    FlavorPane.error     .state-ribbon {
        display: block; background: $error 20%; color: $error;
    }
    """

    def __init__(self, flavor: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.flavor = flavor

    def compose(self) -> ComposeResult:
        with Vertical(id=f"conv-container-{self.flavor}"):
            yield Static("", id=f"ribbon-{self.flavor}", classes="state-ribbon")
            yield SearchBar(id=f"search-{self.flavor}")
            yield ConversationView(id=f"conv-{self.flavor}")
            yield SlashDropdown(id=f"slash-{self.flavor}")
            yield FilePickerDropdown(id=f"files-{self.flavor}")
            yield ChatInput(id=f"input-{self.flavor}")
        yield MonitorSidebar(flavor=self.flavor, id=f"sidebar-{self.flavor}")

    # ── State machine ────────────────────────────────────────────────

    def set_state(self, state: AgentState) -> None:
        for s in AgentState:
            self.remove_class(s.value)
        if state != AgentState.IDLE:
            self.add_class(state.value)
        # Update the redundant in-pane ribbon (#29 item 21).
        try:
            ribbon = self.query_one(f"#ribbon-{self.flavor}", Static)
            label, color = _STATE_RIBBON.get(state, ("", "$primary"))
            ribbon.update(f"[{color}]{label}[/]")
        except Exception:  # noqa: BLE001
            pass

    # ── Conv / sidebar accessors ─────────────────────────────────────

    @property
    def conversation(self) -> ConversationView:
        return self.query_one(f"#conv-{self.flavor}", ConversationView)

    @property
    def sidebar(self) -> MonitorSidebar:
        return self.query_one(f"#sidebar-{self.flavor}", MonitorSidebar)

    @property
    def input(self) -> ChatInput:
        return self.query_one(f"#input-{self.flavor}", ChatInput)

    def sync_sidebar(self, state: FlavorState) -> None:
        self.sidebar.update_from(state)
