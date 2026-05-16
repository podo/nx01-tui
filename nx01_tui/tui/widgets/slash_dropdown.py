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
        dock: top;
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
        self.candidates = (
            list(candidates) if candidates is not None else list(DEFAULT_SLASH_COMMANDS)
        )
        self._populate("")

    def _populate(self, query: str) -> None:
        self.clear_options()
        q = query.lower().lstrip("/")
        for cmd, desc in self.candidates:
            hay = (cmd + " " + desc).lower()
            if q and q not in hay:
                continue
            self.add_option(Option(f"[bold]{cmd}[/]  [dim]{desc}[/]", id=cmd))

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
