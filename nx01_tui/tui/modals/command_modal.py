"""CommandModal — central hub (ctrl+p) with categorized actions + fuzzy search.

Dismisses with a CommandAction string the parent App routes to a handler.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from .base import BaseModal


@dataclass
class CommandEntry:
    action: str  # internal action id the App handles
    label: str
    description: str
    keybind: str = ""
    group: str = ""
    enabled: bool = True


def default_commands() -> list[CommandEntry]:
    return [
        # Quick Actions
        CommandEntry(
            "open_sessions",
            "💬 Sessions",
            "Resume · fork · rename · delete",
            "ctrl+s",
            "Quick Actions",
        ),
        CommandEntry("open_memory", "📝 Memory", "Agent + user profile", "ctrl+m", "Quick Actions"),
        CommandEntry(
            "new_session", "+ New Session", "Start a fresh session", "ctrl+n", "Quick Actions"
        ),
        CommandEntry("open_skills", "⚡ Skills", "List · load · unload", "ctrl+k", "Quick Actions"),
        CommandEntry(
            "open_tools",
            "🔧 Tools & MCP",
            "Tools, toolsets, MCP servers",
            "ctrl+t",
            "Quick Actions",
        ),
        # Flavor
        CommandEntry("switch_flavor", "🤖 Switch Flavor", "Next flavor tab", "Tab", "Flavor"),
        CommandEntry(
            "switch_model", "⚙ Switch Model", "Change the underlying model", "/model", "Flavor"
        ),
        # View
        CommandEntry(
            "toggle_sidebar", "▸ Toggle Sidebar", "Show/hide monitoring sidebar", "ctrl+b", "View"
        ),
        CommandEntry("toggle_theme", "🎨 Toggle Theme", "Dark / light", "d", "View"),
        CommandEntry("search", "🔍 Search", "Search in conversation", "ctrl+f", "View"),
        # System
        CommandEntry("open_cost", "📊 Cost & Tokens", "Usage breakdown", "/cost", "System"),
        CommandEntry("open_config", "⚙ Configuration", "App settings", "/config", "System"),
        CommandEntry("help", "❓ Help", "Keyboard shortcuts", "?", "System"),
        CommandEntry("quit", "🚪 Quit", "Exit the application", "q", "System"),
        # V2 (disabled)
        CommandEntry(
            "v2_cron", "⏰ Cron Jobs", "Scheduled tasks (v2)", "/cron", "V2", enabled=False
        ),
        CommandEntry("v2_kanban", "📋 Kanban", "Board view (v2)", "/kanban", "V2", enabled=False),
        CommandEntry(
            "v2_browser", "🌐 Browser", "Screenshot view (v2)", "/browser", "V2", enabled=False
        ),
        CommandEntry(
            "v2_debug", "🐛 Debug", "Raw SSE event log (v2)", "/debug", "V2", enabled=False
        ),
        CommandEntry(
            "v2_plugins", "🔌 Plugins", "Plugin manager (v2)", "/plugins", "V2", enabled=False
        ),
    ]


class CommandModal(BaseModal):
    """ModalScreen[str] — dismisses with selected action id or empty string."""

    DEFAULT_CSS = """
    CommandModal .dialog { width: 70; height: 90%; }
    CommandModal Input { margin-bottom: 1; }
    CommandModal OptionList { height: 1fr; }
    """

    BINDINGS = [
        Binding("enter", "select", "Select", show=False),
    ]

    def __init__(self, commands: list[CommandEntry] | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.all_commands = commands or default_commands()
        self._visible_actions: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Commands[/]", classes="dialog-title")
            yield Input(placeholder="Filter…", id="filter")
            yield OptionList(*self._render_options(""), id="cmd-list")
            yield Static("[dim]↑↓ navigate · Enter run · ESC close[/]", classes="dialog-hint")

    def _render_options(self, query: str) -> list[Option]:
        q = query.lower().strip()
        opts: list[Option] = []
        self._visible_actions = []
        last_group = None
        for cmd in self.all_commands:
            haystack = f"{cmd.label} {cmd.description} {cmd.keybind}".lower()
            if q and q not in haystack:
                continue
            if cmd.group and cmd.group != last_group:
                opts.append(Option(f"[dim]── {cmd.group} ──[/]", disabled=True))
                last_group = cmd.group
            kb = f"  [dim]{cmd.keybind}[/]" if cmd.keybind else ""
            disabled_tag = "  [dim](v2)[/]" if not cmd.enabled else ""
            opts.append(
                Option(
                    f"{cmd.label}  [dim]{cmd.description}[/]{kb}{disabled_tag}",
                    id=cmd.action,
                    disabled=not cmd.enabled,
                )
            )
            self._visible_actions.append(cmd.action)
        if not opts:
            opts.append(Option("[dim]no matches[/]", disabled=True))
        return opts

    def on_input_changed(self, event: Input.Changed) -> None:
        try:
            lst = self.query_one("#cmd-list", OptionList)
            lst.clear_options()
            for opt in self._render_options(event.value):
                lst.add_option(opt)
        except Exception:  # noqa: BLE001
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        action = event.option.id or ""
        if action:
            self.dismiss(action)

    def action_select(self) -> None:
        try:
            lst = self.query_one("#cmd-list", OptionList)
            opt = lst.get_option_at_index(lst.highlighted or 0)
            if opt and opt.id:
                self.dismiss(opt.id)
        except Exception:  # noqa: BLE001
            pass
