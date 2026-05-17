"""ExpandChevron — ▶ collapsed, ▼ expanded. Bold, 3-cell wide."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class ExpandChevron(Static):
    """Chevron indicating expand/collapse state. Larger filled glyph + bold so
    it reads clearly across all themes."""

    DEFAULT_CSS = """
    ExpandChevron {
        width: 3;
        color: $accent;
        text-style: bold;
        content-align: center middle;
    }
    """

    expanded: reactive[bool] = reactive(False)

    def __init__(self, expanded: bool = False, **kwargs: object) -> None:
        super().__init__("▶", **kwargs)
        self.expanded = expanded

    def watch_expanded(self, value: bool) -> None:
        self.update("▼" if value else "▶")

    def toggle(self) -> bool:
        self.expanded = not self.expanded
        return self.expanded
