"""ExpandChevron — ▸ collapsed, ▾ expanded with 200ms rotation."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class ExpandChevron(Static):
    """Single-cell chevron indicating expand/collapse state."""

    DEFAULT_CSS = """
    ExpandChevron {
        width: 2;
        color: $text-muted;
        content-align: center middle;
    }
    """

    expanded: reactive[bool] = reactive(False)

    def __init__(self, expanded: bool = False, **kwargs: object) -> None:
        super().__init__("▸", **kwargs)
        self.expanded = expanded

    def watch_expanded(self, value: bool) -> None:
        self.update("▾" if value else "▸")

    def toggle(self) -> bool:
        self.expanded = not self.expanded
        return self.expanded
