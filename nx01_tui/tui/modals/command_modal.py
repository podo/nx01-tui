"""CommandModal — central hub (ctrl+p) with categorized actions + fuzzy search.

Dismisses with a CommandAction string the parent App routes to a handler.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import OptionList, Static
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
            "Sessions",
            "Resume · fork · rename · delete",
            "ctrl+s",
            "Quick Actions",
        ),
        CommandEntry("open_memory", "Memory", "Agent + user profile", "ctrl+m", "Quick Actions"),
        CommandEntry(
            "new_session", "New Session", "Start a fresh session", "ctrl+n", "Quick Actions"
        ),
        CommandEntry("open_skills", "Skills", "List · load · unload", "ctrl+k", "Quick Actions"),
        CommandEntry(
            "open_tools",
            "Tools & MCP",
            "Tools, toolsets, MCP servers",
            "ctrl+t",
            "Quick Actions",
        ),
        # Flavor
        CommandEntry("switch_flavor", "Switch Flavor", "Next flavor tab", "Tab", "Flavor"),
        CommandEntry(
            "switch_model", "Switch Model", "Change the underlying model", "/model", "Flavor"
        ),
        # View
        CommandEntry(
            "toggle_sidebar", "Toggle Sidebar", "Show/hide monitoring sidebar", "ctrl+b", "View"
        ),
        CommandEntry("toggle_theme", "Toggle Theme", "Dark / light", "d", "View"),
        CommandEntry("search", "Search", "Search in conversation", "ctrl+f", "View"),
        # System
        CommandEntry("open_cost", "Cost & Tokens", "Usage breakdown", "/cost", "System"),
        CommandEntry("open_config", "Configuration", "App settings", "/config", "System"),
        CommandEntry("help", "Help", "Keyboard shortcuts", "?", "System"),
        CommandEntry(
            "open_debug",
            "Debug",
            "Raw SSE event log",
            "ctrl+shift+d",
            "System",
        ),
        CommandEntry("quit", "Quit", "Exit the application", "q", "System"),
        # V2 (disabled)
        CommandEntry("v2_cron", "Cron Jobs", "Scheduled tasks (v2)", "/cron", "V2", enabled=False),
        CommandEntry("v2_kanban", "Kanban", "Board view (v2)", "/kanban", "V2", enabled=False),
        CommandEntry(
            "v2_browser", "Browser", "Screenshot view (v2)", "/browser", "V2", enabled=False
        ),
        CommandEntry(
            "v2_plugins", "Plugins", "Plugin manager (v2)", "/plugins", "V2", enabled=False
        ),
    ]


class CommandModal(BaseModal):
    """ModalScreen[str] — dismisses with selected action id or empty string.

    List-focused by default. The filter Input has been removed entirely
    in #29 item 14 — the action list is short enough to scan; type-ahead
    on OptionList still works for prefix-match. V2-marked entries are
    hidden as well to keep the visible list actionable.
    """

    DEFAULT_CSS = """
    CommandModal .dialog { width: 70; height: 90%; }
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
            yield OptionList(*self._render_options(), id="cmd-list")
            yield Static(
                "[dim]↑↓ navigate · Enter run · ESC close[/]",
                classes="dialog-hint",
            )

    def on_mount(self) -> None:
        try:
            self.query_one("#cmd-list", OptionList).focus()
        except Exception:  # noqa: BLE001
            pass

    def _render_options(self) -> list[Option]:
        opts: list[Option] = []
        self._visible_actions = []
        last_group = None
        for cmd in self.all_commands:
            # Hide V2-marked rows entirely (#29 item 14).
            if not cmd.enabled:
                continue
            if cmd.group and cmd.group != last_group:
                opts.append(Option(f"[dim]── {cmd.group} ──[/]", disabled=True))
                last_group = cmd.group
            kb = f"  [dim]{cmd.keybind}[/]" if cmd.keybind else ""
            opts.append(
                Option(
                    f"{cmd.label}  [dim]{cmd.description}[/]{kb}",
                    id=cmd.action,
                )
            )
            self._visible_actions.append(cmd.action)
        if not opts:
            opts.append(Option("[dim]no commands available[/]", disabled=True))
        return opts

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
