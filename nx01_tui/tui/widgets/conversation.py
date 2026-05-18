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

from textual.containers import Vertical, VerticalScroll
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


MAX_MOUNTED_TURNS = 30


class _TurnGroup(Vertical):
    DEFAULT_CSS = "_TurnGroup { height: auto; }"


class _LoadMoreHeader(Static):
    DEFAULT_CSS = """
    _LoadMoreHeader {
        height: 1;
        text-align: center;
        color: $text-muted;
        margin: 1 0;
    }
    _LoadMoreHeader:hover { color: $primary; }
    """

    def __init__(self, count: int, **kwargs: object) -> None:
        label = f"── {count} older turn{'s' if count != 1 else ''} · click to load ──"
        super().__init__(f"[dim]{label}[/]", **kwargs)

    def on_click(self, _event: object) -> None:
        if isinstance(self.parent, ConversationView):
            self.parent._load_archived_turns()


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
        self._scroll_pending: bool = False
        self._current_group: _TurnGroup | None = None
        self._mounted_groups: list[_TurnGroup] = []
        self._archived_groups: list[_TurnGroup] = []
        self._load_header: _LoadMoreHeader | None = None
        self._last_assistant: AssistantMessage | None = None

    def on_mount(self) -> None:
        self._empty_state = _EmptyState(_EMPTY_HINT)
        self.mount(self._empty_state)
        self.set_interval(0.1, self._flush_scroll)

    def _request_scroll(self) -> None:
        self._scroll_pending = True

    def _flush_scroll(self) -> None:
        if self._scroll_pending:
            self.scroll_end(animate=False)
            self._scroll_pending = False

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
        self._current_group = None
        self._mounted_groups = []
        self._archived_groups = []
        self._load_header = None
        self._last_assistant = None

    # ── Turn grouping & paging ───────────────────────────────────────

    def _mount_into_turn(self, widget) -> None:
        """Mount widget into current TurnGroup, or directly if no group started."""
        if self._current_group is not None:
            self._current_group.mount(widget)
        else:
            self.mount(widget)

    def _start_new_turn(self) -> None:
        group = _TurnGroup()
        self._current_group = group
        self._mounted_groups.append(group)
        self.mount(group)
        self._maybe_archive_oldest()

    def _maybe_archive_oldest(self) -> None:
        if len(self._mounted_groups) > MAX_MOUNTED_TURNS:
            oldest = self._mounted_groups.pop(0)
            self._archived_groups.append(oldest)
            oldest.remove()
            self._update_load_header()

    def _update_load_header(self) -> None:
        n = len(self._archived_groups)
        if n == 0:
            if self._load_header is not None:
                self._load_header.remove()
                self._load_header = None
            return
        if self._load_header is None:
            self._load_header = _LoadMoreHeader(n)
            self.mount(self._load_header, before=0)
        else:
            label = f"── {n} older turn{'s' if n != 1 else ''} · click to load ──"
            self._load_header.update(f"[dim]{label}[/]")

    def _load_archived_turns(self) -> None:
        if not self._archived_groups:
            return
        anchor = self._mounted_groups[0] if self._mounted_groups else None
        for group in self._archived_groups:
            if anchor is not None:
                self.mount(group, before=anchor)
            else:
                self.mount(group)
            self._mounted_groups.insert(0, group)
        self._archived_groups = []
        if self._load_header is not None:
            self._load_header.remove()
            self._load_header = None

    def _freeze_last_assistant(self) -> None:
        if self._last_assistant is not None:
            self._last_assistant.freeze()
            self._last_assistant = None

    # ── Public API ───────────────────────────────────────────────────

    def add_user_message(self, text: str) -> UserMessage:
        self._clear_empty_state()
        self._freeze_last_assistant()
        self._start_new_turn()
        widget = UserMessage(text)
        self._mount_into_turn(widget)
        self.scroll_end(animate=False)
        # Reset per-turn references
        self._active_thinking = None
        self._active_assistant = None
        self._active_tools = {}
        return widget

    def start_thinking(self) -> ThinkingBlock:
        if self._active_thinking is None:
            self._clear_empty_state()
            self._active_thinking = ThinkingBlock()
            self._mount_into_turn(self._active_thinking)
        return self._active_thinking

    def append_thinking(self, text: str) -> None:
        block = self.start_thinking()
        block.append_chunk(text)
        self._request_scroll()

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
        self._mount_into_turn(block)
        self.scroll_end(animate=False)
        return block

    def get_tool(self, call_id: str) -> ToolCallBlock | None:
        return self._active_tools.get(call_id)

    def start_skill(self, name: str, size: int = 0) -> SkillBlock:
        block = SkillBlock(skill_name=name, skill_size=size)
        self._mount_into_turn(block)
        self.scroll_end(animate=False)
        return block

    def start_assistant(self, initial: str = "") -> AssistantMessage:
        if self._active_assistant is None:
            self._active_assistant = AssistantMessage(initial)
            self._mount_into_turn(self._active_assistant)
        return self._active_assistant

    def append_assistant(self, text: str) -> None:
        msg = self.start_assistant()
        msg.append(text)
        self._request_scroll()

    def end_assistant(self) -> None:
        if self._active_assistant is None:
            return
        msg = self._active_assistant
        msg.finalise()
        self._active_assistant = None
        self._last_assistant = msg
        # Split fenced code blocks out into clickable CodeBlocks at end-of-turn.
        # The assistant message still renders prose; for each fenced block we
        # also mount a CodeBlock right after for click-to-copy.
        text = getattr(msg, "_buffer", "")
        for match in _FENCE_RE.finditer(text):
            lang, code = match.group(1) or "text", match.group(2).strip()
            if code:
                self._mount_into_turn(CodeBlock(code=code, language=lang))
        self.scroll_end(animate=False)

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
