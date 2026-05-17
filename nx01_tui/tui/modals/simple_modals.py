"""Simple modal stubs — SkillsModal, ToolsModal, ConfigModal, CostModal, ModelPickerModal.

V1 ships minimal versions of these; V2 epics extend them.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
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
                    opts.append(
                        Option(
                            f"[$accent]◆[/] [bold]{name}[/]  {loaded}  [dim]{kb}[/]",
                            id=name,
                        )
                    )
            else:
                opts.append(Option("[dim]no skills available[/]", disabled=True))
            yield OptionList(*opts)
            yield Static("[dim]enter toggle · / filter · ESC close[/]", classes="dialog-hint")


class ToolsModal(BaseModal):
    DEFAULT_CSS = """ToolsModal .dialog { width: 60; height: 80%; }"""

    def __init__(self, tools: list[dict], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.tools = tools

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Tools[/]", classes="dialog-title")
            # Soft callout for v2 deferral (#29 item 29) — kept out of the
            # action-oriented hint line.
            yield Static(
                "[dim italic]MCP and Toolsets tabs land in V2.[/]",
                classes="dialog-callout",
            )
            opts: list[Option] = []
            for t in self.tools or []:
                name = t.get("name", "?")
                desc = t.get("description", "")
                opts.append(Option(f"[$success]▸[/] [bold]{name}[/]  [dim]{desc[:50]}[/]"))
            if not opts:
                opts.append(Option("[dim]no tools available[/]", disabled=True))
            yield OptionList(*opts)
            yield Static("[dim]ESC close[/]", classes="dialog-hint")


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
    """Token + USD breakdown — two-column session vs lifetime split (#29 item 13)."""

    DEFAULT_CSS = """
    CostModal .dialog { width: 70; min-width: 70; height: auto; }
    CostModal #cols { height: auto; }
    CostModal .col { width: 1fr; padding: 0 1; }
    CostModal .col-title { color: $primary; text-style: bold; margin-bottom: 1; }
    CostModal .row { height: 1; }
    CostModal #ratio-bar { color: $primary; margin: 1 0 0 0; }
    """

    _BAR_WIDTH = 24

    def __init__(self, cost: dict, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.cost = cost or {}

    def _section_rows(self, header: str, data: dict) -> list[Static]:
        inp = int(data.get("input_tokens", data.get("input", 0)))
        out = int(data.get("output_tokens", data.get("output", 0)))
        cached = int(data.get("cached_tokens", data.get("cached", 0)))
        usd = float(data.get("total_cost_usd", data.get("usd", 0.0)))
        rows = [
            Static(f"[bold]{header}[/]", classes="col-title"),
            Static(f"[dim]Input    [/] {inp:>10,}", classes="row"),
            Static(f"[dim]Output   [/] {out:>10,}", classes="row"),
            Static(f"[dim]Cached   [/] {cached:>10,}", classes="row"),
            Static(f"[dim]Cost     [/] ${usd:>9,.4f}", classes="row"),
        ]
        return rows

    def _ratio_bar(self) -> str:
        # In/out ratio bar — primary for input, accent for output.
        inp = int(self.cost.get("input_tokens", self.cost.get("input", 0)))
        out = int(self.cost.get("output_tokens", self.cost.get("output", 0)))
        total = inp + out
        if total == 0:
            return ""
        in_w = max(1, int(round(self._BAR_WIDTH * inp / total))) if inp else 0
        out_w = self._BAR_WIDTH - in_w
        return (
            f"[$primary]{'█' * in_w}[/][$accent]{'█' * out_w}[/]  "
            f"[dim]in {inp / total:.0%} · out {out / total:.0%}[/]"
        )

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Cost & Tokens[/]", classes="dialog-title")
            with Horizontal(id="cols"):
                with Vertical(classes="col"):
                    for row in self._section_rows("This session", self.cost):
                        yield row
                with Vertical(classes="col"):
                    lifetime = self.cost.get("lifetime", self.cost)
                    for row in self._section_rows("Lifetime", lifetime):
                        yield row
            yield Static(self._ratio_bar(), id="ratio-bar")
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
