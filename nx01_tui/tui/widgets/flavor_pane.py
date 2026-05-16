"""FlavorPane — horizontal container holding ConversationView + MonitorSidebar.

One per flavor tab. State class on the root drives border color transitions.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical

from ..state import AgentState, FlavorState
from .chat_input import ChatInput
from .conversation import ConversationView
from .search_bar import SearchBar
from .sidebar import MonitorSidebar


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
    """

    def __init__(self, flavor: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.flavor = flavor

    def compose(self) -> ComposeResult:
        with Vertical(id=f"conv-container-{self.flavor}"):
            yield SearchBar(id=f"search-{self.flavor}")
            yield ConversationView(id=f"conv-{self.flavor}")
            yield ChatInput(id=f"input-{self.flavor}")
        yield MonitorSidebar(flavor=self.flavor, id=f"sidebar-{self.flavor}")

    # ── State machine ────────────────────────────────────────────────

    def set_state(self, state: AgentState) -> None:
        for s in AgentState:
            self.remove_class(s.value)
        if state != AgentState.IDLE:
            self.add_class(state.value)

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
