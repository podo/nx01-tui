"""ConversationView — scrollable container hosting all conversation widgets.

Provides a small API the App layer uses without poking at internals:

    conv.add_user_message(text)
    conv.start_thinking()        → ThinkingBlock
    conv.start_tool(tool, args)  → ToolCallBlock
    conv.start_skill(name, size) → SkillBlock
    conv.start_assistant()       → AssistantMessage (streaming)
"""

from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager

from textual.containers import VerticalScroll
from textual.widgets import Static

from .code_block import CodeBlock
from .messages import AssistantMessage, UserMessage
from .search_bar import SearchBar
from .skill_block import SkillBlock
from .thinking_block import ThinkingBlock
from .tool_call_block import ToolCallBlock

_FENCE_RE = re.compile(r"```(\w+)?\n(.*?)\n```", re.DOTALL)


class UnreadDivider(Static):
    DEFAULT_CSS = """
    UnreadDivider {
        height: 1;
        text-align: center;
        color: $warning;
        margin: 1 0;
    }
    """


_EMPTY_HINT = (
    "[bold]Welcome to nx01-tui[/]\n\n"
    "[dim]Type a message and press [bold]Enter[/] to send · [bold]Shift+Enter[/] for newline.\n"
    "[bold]ctrl+p[/] command palette · [bold]?[/] help · [bold]ctrl+q[/] quit[/]"
)


class _EmptyState(Static):
    DEFAULT_CSS = """
    _EmptyState {
        content-align: center middle;
        text-align: center;
        color: $text-muted;
        height: 1fr;
        padding: 4 2;
    }
    """


class ConversationView(VerticalScroll):
    DEFAULT_CSS = """
    ConversationView {
        padding: 1 2;
        height: 1fr;
        background: $background;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._active_thinking: ThinkingBlock | None = None
        self._active_assistant: AssistantMessage | None = None
        self._active_tools: dict[str, ToolCallBlock] = {}
        self._empty_state: _EmptyState | None = None
        self._unread_divider: UnreadDivider | None = None
        self._scroll_suppress_depth: int = 0

    @contextmanager
    def suppress_scroll(self) -> Generator[None, None, None]:
        """Suppress scroll_end calls during batch operations. Re-entrant safe."""
        self._scroll_suppress_depth += 1
        try:
            yield
        finally:
            self._scroll_suppress_depth -= 1

    def _maybe_scroll(self) -> None:
        if self._scroll_suppress_depth == 0:
            self.scroll_end(animate=False)

    def on_mount(self) -> None:
        self._empty_state = _EmptyState(_EMPTY_HINT)
        self.mount(self._empty_state)

    def _clear_empty_state(self) -> None:
        if self._empty_state is not None:
            self._empty_state.remove()
            self._empty_state = None

    def reset_for_replay(self) -> None:
        """Wipe all rendered children + per-turn state. Used before a
        session-history replay (W7 in podo/nx01-tui#26) so we start from
        an empty conversation column.
        """
        self.remove_children()
        self._empty_state = None
        self._active_thinking = None
        self._active_assistant = None
        self._active_tools = {}
        self._unread_divider = None

    # ── Public API ───────────────────────────────────────────────────

    def add_user_message(self, text: str) -> UserMessage:
        self._clear_empty_state()
        widget = UserMessage(text)
        self.mount(widget)
        self._maybe_scroll()
        # Reset per-turn references
        self._active_thinking = None
        self._active_assistant = None
        self._active_tools = {}
        return widget

    def start_thinking(self) -> ThinkingBlock:
        if self._active_thinking is None:
            self._clear_empty_state()
            self._active_thinking = ThinkingBlock()
            self.mount(self._active_thinking)
        return self._active_thinking

    def append_thinking(self, text: str) -> None:
        block = self.start_thinking()
        block.append_chunk(text)
        self._maybe_scroll()

    def end_thinking(self, auto_collapse: bool = True) -> None:
        if self._active_thinking is not None:
            self._active_thinking.done(auto_collapse=auto_collapse)
            self._active_thinking = None

    def insert_unread_divider(self, count: int) -> UnreadDivider:
        label = f"── {count} new message{'s' if count != 1 else ''} since last visit ──"
        self._unread_divider = UnreadDivider(f"[bold $warning]{label}[/]")
        self.mount(self._unread_divider)
        return self._unread_divider

    def scroll_to_unread_after_refresh(self) -> None:
        if self._unread_divider is not None:
            divider = self._unread_divider
            self.call_after_refresh(lambda: self.scroll_to_widget(divider, animate=False))

    def start_tool(self, tool: str, args: str = "", call_id: str = "") -> ToolCallBlock:
        if call_id and call_id in self._active_tools:
            return self._active_tools[call_id]
        self._clear_empty_state()
        block = ToolCallBlock(tool=tool, args=args, call_id=call_id)
        if call_id:
            self._active_tools[call_id] = block
        self.mount(block)
        self._maybe_scroll()
        return block

    def get_tool(self, call_id: str) -> ToolCallBlock | None:
        return self._active_tools.get(call_id)

    def start_skill(self, name: str, size: int = 0) -> SkillBlock:
        block = SkillBlock(skill_name=name, skill_size=size)
        self.mount(block)
        self._maybe_scroll()
        return block

    def start_assistant(self, initial: str = "") -> AssistantMessage:
        if self._active_assistant is None:
            self._active_assistant = AssistantMessage(initial)
            self.mount(self._active_assistant)
        return self._active_assistant

    def append_assistant(self, text: str) -> None:
        msg = self.start_assistant()
        msg.append(text)
        self._maybe_scroll()

    def end_assistant(self) -> None:
        if self._active_assistant is None:
            return
        msg = self._active_assistant
        msg.finalise()
        self._active_assistant = None
        # Split fenced code blocks out into clickable CodeBlocks at end-of-turn.
        # The assistant message still renders prose; for each fenced block we
        # also mount a CodeBlock right after for click-to-copy.
        text = getattr(msg, "_buffer", "")
        for match in _FENCE_RE.finditer(text):
            lang, code = match.group(1) or "text", match.group(2).strip()
            if code:
                self.mount(CodeBlock(code=code, language=lang))
        self._maybe_scroll()

    # ── Search bar control ───────────────────────────────────────────

    def show_search(self) -> None:
        bar = self._search_bar()
        bar.show()

    def hide_search(self) -> None:
        bar = self._search_bar()
        bar.hide()

    def _search_bar(self) -> SearchBar:
        try:
            return self.query_one(SearchBar)
        except Exception:  # noqa: BLE001
            bar = SearchBar()
            self.mount(bar, before=0)
            return bar
