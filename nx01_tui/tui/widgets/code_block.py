"""CodeBlock — clickable fenced-code widget that copies on click.

Mounted by ConversationView when the assistant emits a fenced ```code```
block in its markdown stream. Renders with syntax highlighting via
rich.syntax and emits a Copied message on click.
"""

from __future__ import annotations

from rich.syntax import Syntax
from textual.message import Message
from textual.widgets import Static


class CodeBlock(Static):
    DEFAULT_CSS = """
    CodeBlock {
        border: round $panel;
        padding: 0 1;
        margin: 0 0 1 0;
        background: $surface;
        height: auto;
    }
    CodeBlock:hover {
        border: round $primary;
        background: $boost;
    }
    """

    class Copied(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(
        self,
        code: str,
        language: str | None = None,
        **kwargs: object,
    ) -> None:
        self._code = code
        self._language = language or "text"
        syntax = Syntax(
            code,
            self._language,
            theme="ansi_dark",
            line_numbers=False,
            word_wrap=True,
        )
        super().__init__(syntax, **kwargs)
        self.tooltip = f"click to copy ({len(code)} chars)"

    @property
    def code(self) -> str:
        return self._code

    def on_click(self) -> None:
        try:
            self.app.copy_to_clipboard(self._code)
            self.notify(f"Copied {len(self._code)} chars")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Copy failed: {exc}", severity="error")
        self.post_message(self.Copied(self._code))
