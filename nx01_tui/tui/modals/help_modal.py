"""HelpModal — auto-generated keybinding table."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from .base import BaseModal

_KEYBINDINGS: list[tuple[str, str, str]] = [
    # (group, key, action)
    ("Global", "ctrl+p", "Command Modal"),
    ("Global", "ctrl+s", "Sessions"),
    ("Global", "ctrl+m", "Memory"),
    ("Global", "ctrl+k", "Skills"),
    ("Global", "ctrl+t", "Tools"),
    ("Global", "ctrl+n", "New session"),
    ("Global", "ctrl+b", "Toggle sidebar"),
    ("Global", "ctrl+f", "Search"),
    ("Global", "ctrl+c", "Stop generation"),
    ("Global", "Tab", "Next flavor"),
    ("Global", "Shift+Tab", "Prev flavor"),
    ("Global", "?", "This help"),
    ("Global", "q", "Quit"),
    ("Global", "d", "Toggle theme"),
    ("Global", "ESC", "Pop modal / dismiss"),
    ("Conversation", "↑ ↓ PgUp PgDn", "Scroll"),
    ("Conversation", "x / space", "Toggle expand"),
    ("Conversation", "y", "Yank focused block"),
    ("Conversation", "Y", "Yank last code block"),
    ("Conversation", "n / N", "Next / prev search match"),
    ("Input", "Enter", "Send message"),
    ("Input", "Shift+Enter", "Newline (modern term.)"),
    ("Input", "Alt+Enter", "Newline (Terminal.app fallback)"),
    ("Input", "ctrl+j", "Send (universal fallback)"),
    ("Input", "/", "Slash command"),
    ("Sessions", "r / f / e / d", "Resume / Fork / Edit / Delete"),
    ("Permission", "y / n / a", "Allow / Deny / Always"),
]


class HelpModal(BaseModal):
    DEFAULT_CSS = """
    HelpModal .dialog { width: 70; height: 90%; }
    HelpModal DataTable { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Keyboard Shortcuts[/]", classes="dialog-title")
            table: DataTable = DataTable(zebra_stripes=True, cursor_type="none")
            table.add_columns("Group", "Key", "Action")
            for group, key, action in _KEYBINDINGS:
                table.add_row(group, f"[bold]{key}[/]", action)
            yield table
            yield Static("[dim]ESC to close[/]", classes="dialog-hint")
