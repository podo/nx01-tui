"""ConversationView — scrollable container hosting all conversation widgets.

Provides a small API the App layer uses without poking at internals:

    conv.add_user_message(text)
    conv.start_thinking()        → ThinkingBlock
    conv.start_tool(tool, args)  → ToolCallBlock
    conv.start_skill(name, size) → SkillBlock
    conv.start_assistant()       → AssistantMessage (streaming)
"""

from __future__ import annotations

from textual.containers import VerticalScroll

from .messages import AssistantMessage, UserMessage
from .search_bar import SearchBar
from .skill_block import SkillBlock
from .thinking_block import ThinkingBlock
from .tool_call_block import ToolCallBlock


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

    # ── Public API ───────────────────────────────────────────────────

    def add_user_message(self, text: str) -> UserMessage:
        widget = UserMessage(text)
        self.mount(widget)
        self.scroll_end(animate=False)
        # Reset per-turn references
        self._active_thinking = None
        self._active_assistant = None
        self._active_tools = {}
        return widget

    def start_thinking(self) -> ThinkingBlock:
        if self._active_thinking is None:
            self._active_thinking = ThinkingBlock()
            self.mount(self._active_thinking)
        return self._active_thinking

    def append_thinking(self, text: str) -> None:
        block = self.start_thinking()
        block.append_chunk(text)
        self.scroll_end(animate=False)

    def end_thinking(self) -> None:
        if self._active_thinking is not None:
            self._active_thinking.done()
            self._active_thinking = None

    def start_tool(self, tool: str, args: str = "", call_id: str = "") -> ToolCallBlock:
        if call_id and call_id in self._active_tools:
            return self._active_tools[call_id]
        block = ToolCallBlock(tool=tool, args=args, call_id=call_id)
        if call_id:
            self._active_tools[call_id] = block
        self.mount(block)
        self.scroll_end(animate=False)
        return block

    def get_tool(self, call_id: str) -> ToolCallBlock | None:
        return self._active_tools.get(call_id)

    def start_skill(self, name: str, size: int = 0) -> SkillBlock:
        block = SkillBlock(skill_name=name, skill_size=size)
        self.mount(block)
        self.scroll_end(animate=False)
        return block

    def start_assistant(self, initial: str = "") -> AssistantMessage:
        if self._active_assistant is None:
            self._active_assistant = AssistantMessage(initial)
            self.mount(self._active_assistant)
        return self._active_assistant

    def append_assistant(self, text: str) -> None:
        msg = self.start_assistant()
        msg.append(text)
        self.scroll_end(animate=False)

    def end_assistant(self) -> None:
        if self._active_assistant is not None:
            self._active_assistant.finalise()
            self._active_assistant = None

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
