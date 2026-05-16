"""Simple modal stubs — SkillsModal, ToolsModal, ConfigModal, CostModal, ModelPickerModal.

V1 ships minimal versions of these; V2 epics extend them.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from .base import BaseModal


class SkillsModal(BaseModal):
    DEFAULT_CSS = """SkillsModal .dialog { width: 60; height: 80%; }"""

    def __init__(self, skills: list[dict], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.skills = skills

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Skills[/]", classes="dialog-title")
            opts: list[Option] = []
            if self.skills:
                for s in self.skills:
                    name = s.get("name", "?")
                    size = s.get("size", 0)
                    loaded = "[$success]●[/] loaded" if s.get("loaded") else "[dim]○[/] available"
                    kb = f"{size / 1024:.1f}kb" if size else ""
                    opts.append(Option(f"⚡ [bold]{name}[/]  {loaded}  [dim]{kb}[/]"))
            else:
                opts.append(Option("[dim]no skills available[/]", disabled=True))
            yield OptionList(*opts)
            yield Static("[dim]ESC close[/]", classes="dialog-hint")


class ToolsModal(BaseModal):
    DEFAULT_CSS = """ToolsModal .dialog { width: 60; height: 80%; }"""

    def __init__(self, tools: list[dict], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.tools = tools

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Tools[/]", classes="dialog-title")
            opts: list[Option] = []
            for t in self.tools or []:
                name = t.get("name", "?")
                desc = t.get("description", "")
                opts.append(Option(f"🔧 [bold]{name}[/]  [dim]{desc[:50]}[/]"))
            if not opts:
                opts.append(Option("[dim]no tools available[/]", disabled=True))
            yield OptionList(*opts)
            yield Static(
                "[dim]MCP and Toolsets tabs land in V2 · ESC close[/]", classes="dialog-hint"
            )


class ConfigModal(BaseModal):
    DEFAULT_CSS = """ConfigModal .dialog { width: 60; height: auto; }"""

    def __init__(self, config: dict, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Configuration[/]", classes="dialog-title")
            lines = "\n".join(f"[dim]{k}:[/] {v}" for k, v in (self.config or {}).items())
            yield Static(lines or "[dim]no config loaded[/]")
            yield Static(
                "[dim]Edit via /set /get /unset slash commands · ESC close[/]",
                classes="dialog-hint",
            )


class CostModal(BaseModal):
    DEFAULT_CSS = """CostModal .dialog { width: 60; height: auto; }"""

    def __init__(self, cost: dict, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.cost = cost

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Cost & Tokens[/]", classes="dialog-title")
            tokens = self.cost.get("tokens", {}) if self.cost else {}
            inp = tokens.get("input", 0)
            out = tokens.get("output", 0)
            total = tokens.get("total", inp + out)
            yield Static(f"[dim]Input tokens:[/]  {inp:,}")
            yield Static(f"[dim]Output tokens:[/] {out:,}")
            yield Static(f"[dim]Total tokens:[/]  {total:,}")
            if "usd" in (self.cost or {}):
                yield Static(f"[dim]Estimated cost:[/] ${self.cost['usd']:.4f}")
            yield Static("[dim]ESC close[/]", classes="dialog-hint")


class ModelPickerModal(BaseModal):
    """ModalScreen[str] — dismisses with selected model name."""

    DEFAULT_CSS = """ModelPickerModal .dialog { width: 60; height: 70%; }"""

    def __init__(self, models: list[str], current: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.models = models
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Switch Model[/]", classes="dialog-title")
            opts = [
                Option(
                    f"{'[$success]●[/]' if m == self.current else ' '} [bold]{m}[/]",
                    id=m,
                )
                for m in self.models
            ]
            if not opts:
                opts.append(Option("[dim]no models available[/]", disabled=True))
            yield OptionList(*opts, id="model-list")
            yield Static("[dim]Enter to select · ESC close[/]", classes="dialog-hint")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.dismiss(event.option.id)
