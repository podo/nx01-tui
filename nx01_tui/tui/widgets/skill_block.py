"""SkillBlock — purple-bordered collapsible block when Hermes loads a skill."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Markdown, Static

from .chevron import ExpandChevron


class SkillBlock(Vertical):
    DEFAULT_CSS = """
    SkillBlock {
        border: round $accent;
        margin: 0 0 1 0;
        padding: 0 1;
        height: auto;
        opacity: 0.85;
    }
    SkillBlock.done { opacity: 0.7; }
    SkillBlock #header { height: 1; }
    SkillBlock #header > ExpandChevron     { width: 3; }
    SkillBlock #header > Static#icon       { width: 2; color: $accent; }
    SkillBlock #header > Static#label      { width: 1fr; color: $accent; }
    SkillBlock #header > Static#size       { width: auto; color: $text-muted; }
    SkillBlock Markdown {
        height: auto;
        max-height: 16;
        background: transparent;
    }
    SkillBlock.collapsed Markdown { display: none; }
    """

    collapsed: reactive[bool] = reactive(True)

    def __init__(
        self, skill_name: str, skill_size: int = 0, content: str = "", **kwargs: object
    ) -> None:
        super().__init__(**kwargs)
        self.skill_name = skill_name
        self.skill_size = skill_size
        self.content = content or "_Loading skill manifest…_"
        self.add_class("collapsed")

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield ExpandChevron(expanded=False)
            yield Static("◆", id="icon")
            yield Static(f"[bold]skill:{self.skill_name}[/]  [dim]loaded[/]", id="label")
            yield Static(self._size_text(), id="size")
        yield Markdown(self.content)

    def _size_text(self) -> str:
        if not self.skill_size:
            return ""
        kb = self.skill_size / 1024
        return f"[dim]{kb:.1f}kb[/]"

    def set_content(self, content: str) -> None:
        self.content = content
        try:
            self.query_one(Markdown).update(content)
        except Exception:  # noqa: BLE001
            pass

    def set_collapsed(self, collapsed: bool) -> None:
        self.collapsed = collapsed
        if collapsed:
            self.add_class("collapsed")
        else:
            self.remove_class("collapsed")
        try:
            self.query_one(ExpandChevron).expanded = not collapsed
        except Exception:  # noqa: BLE001
            pass

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self.collapsed)

    def on_click(self, event: events.Click) -> None:
        # Header subtree only.
        node = event.widget
        while node is not None and node is not self:
            if getattr(node, "id", None) == "header":
                self.toggle_collapsed()
                return
            node = node.parent
