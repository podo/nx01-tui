"""SlashDropdown — autocomplete dropdown that watches a TextArea.

textual-autocomplete v4 only supports `Input`, but our `ChatInput` is a
`TextArea` (multi-line). This is a focused replacement: a floating list
above the input that filters slash commands as the user types.
"""

from __future__ import annotations

from textual import on
from textual.binding import Binding
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

# Default slash command list — overridden per-flavor from /help when
# the backend exposes a discovery endpoint (backend gap #16).
DEFAULT_SLASH_COMMANDS: list[tuple[str, str]] = [
    ("/help", "show help"),
    ("/new", "start a new session"),
    ("/resume", "resume a session"),
    ("/fork", "fork from current session"),
    ("/sessions", "list sessions"),
    ("/title", "rename current session"),
    ("/history", "scrollback"),
    ("/context", "show context window usage"),
    ("/compact", "compact conversation history"),
    ("/memory", "view agent memory"),
    ("/memory add", "add an entry to memory"),
    ("/memory remove", "remove an entry from memory"),
    ("/memory replace", "replace an entry in memory"),
    ("/user", "view user profile memory"),
    ("/user add", "add to user profile"),
    ("/tools", "list tools"),
    ("/skills", "list skills"),
    ("/skill load", "load a skill"),
    ("/model", "switch model"),
    ("/config", "view configuration"),
    ("/cost", "show cost breakdown"),
    ("/tokens", "show token usage"),
    ("/status", "show flavor status"),
    ("/version", "show version"),
    ("/whoami", "show identity"),
    ("/set", "set a config key"),
    ("/get", "read a config key"),
    ("/unset", "unset a config key"),
]


class SlashDropdown(OptionList):
    """Auto-hides; shown only while target text starts with `/`."""

    DEFAULT_CSS = """
    SlashDropdown {
        display: none;
        height: auto;
        max-height: 8;
        border: round $panel;
        background: $surface;
    }
    SlashDropdown.visible { display: block; }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("tab", "complete", "Complete", show=False),
        Binding("enter", "complete", "Complete", show=False),
    ]

    class Completed(Message):
        """The user accepted a suggestion."""

        def __init__(self, command: str) -> None:
            super().__init__()
            self.command = command

    def __init__(
        self,
        candidates: list[tuple[str, str]] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        # Each candidate is (insertion_string, description, category) where
        # category is one of "cmd" / "skill" / "tool". Two-tuples coming in
        # via the legacy DEFAULT_SLASH_COMMANDS list are normalised to
        # category="cmd".
        seed = candidates if candidates is not None else DEFAULT_SLASH_COMMANDS
        self.candidates: list[tuple[str, str, str]] = [
            (item[0], item[1], item[2] if len(item) > 2 else "cmd")  # type: ignore[misc]
            for item in seed
        ]
        self._populate("")

    def set_sources(
        self,
        commands: list[dict] | None = None,
        skills: list[dict] | None = None,
        tools: list[dict] | None = None,
    ) -> None:
        """Bootstrap the dropdown from live backend data.

        Each entry inserts a categorised string at completion (D8 in
        podo/nx01-tui#26):

            commands   →  /<name>
            skills     →  /skill <name>
            tools      →  /tool <name>
        """
        merged: list[tuple[str, str, str]] = []
        for cmd in commands or []:
            name = cmd.get("name") or ""
            if not name:
                continue
            insertion = name if name.startswith("/") else f"/{name}"
            merged.append((insertion, cmd.get("description", ""), "cmd"))
        for sk in skills or []:
            name = sk.get("name") or ""
            if not name:
                continue
            loaded = "loaded" if sk.get("loaded") else "available"
            merged.append((f"/skill {name}", loaded, "skill"))
        # /tools may return {tools: [...]} or a bare list of dicts.
        tool_list = tools or []
        for t in tool_list:
            name = t.get("name") if isinstance(t, dict) else None
            if not name:
                continue
            desc = t.get("description", "") if isinstance(t, dict) else ""
            merged.append((f"/tool {name}", desc, "tool"))
        self.candidates = merged or list(self.candidates)
        self._populate("")

    # Category → semantic colour (#29 item 12).
    _CATEGORY_LABEL = {"cmd": "cmd", "skill": "skill", "tool": "tool"}
    _CATEGORY_COLOR = {
        "cmd": "$primary",
        "skill": "$accent",
        "tool": "$success",
    }

    def _populate(self, query: str) -> None:
        self.clear_options()
        q = query.lower().lstrip("/")
        # Filter first so the insertion column width matches what's visible.
        visible: list[tuple[str, str, str]] = []
        for entry in self.candidates:
            insertion, desc, category = entry
            if q and q not in (insertion + " " + desc).lower():
                continue
            visible.append(entry)
        # Column rhythm (#29 item 23): pad insertion to a stable width per
        # the longest visible entry, cap at 32 cells.
        max_w = min(32, max((len(i) for i, _, _ in visible), default=10))
        for insertion, desc, category in visible:
            cat_label = self._CATEGORY_LABEL.get(category, category)
            cat_color = self._CATEGORY_COLOR.get(category, "$accent")
            padded = insertion.ljust(max_w)
            label = (
                f"[bold]{padded}[/]  [dim]{desc}[/]  "
                f"[{cat_color}][[/][{cat_color}] {cat_label:<5}[/][{cat_color}]][/]"
            )
            self.add_option(Option(label, id=insertion))

    def update_for_text(self, text: str) -> None:
        """Show / hide based on prefix; refresh suggestions."""
        if text.startswith("/"):
            self._populate(text)
            if self.option_count > 0:
                self.add_class("visible")
                if self.highlighted is None:
                    self.highlighted = 0
            else:
                self.remove_class("visible")
        else:
            self.remove_class("visible")

    def action_dismiss(self) -> None:
        self.remove_class("visible")

    def action_complete(self) -> None:
        if self.highlighted is None or self.option_count == 0:
            return
        opt = self.get_option_at_index(self.highlighted)
        if opt and opt.id:
            self.post_message(self.Completed(opt.id))
            self.remove_class("visible")

    @on(OptionList.OptionSelected)
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.post_message(self.Completed(event.option.id))
            self.remove_class("visible")
