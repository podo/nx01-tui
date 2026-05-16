"""PermissionModal — blocks SSE stream until user approves/denies/always.

Pushed via `await app.push_screen_wait(PermissionModal(...))` from inside
the SSE worker. Returns one of "allow" | "deny" | "always_allow".
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from .base import BaseModal


class PermissionModal(BaseModal):
    DEFAULT_CSS = """
    PermissionModal .dialog {
        width: 64;
        border: thick $error;
    }
    PermissionModal Button { margin: 0 1; }
    PermissionModal #risk {
        color: $warning;
        margin-bottom: 1;
    }
    PermissionModal #description {
        color: $text-muted;
        margin: 1 0;
    }
    """

    BINDINGS = [
        Binding("y", "allow", "Allow", show=False),
        Binding("n", "deny", "Deny", show=False),
        Binding("a", "always_allow", "Always allow", show=False),
    ]

    def __init__(
        self,
        tool: str,
        args: str,
        risk: str = "low",
        description: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.tool = tool
        self.args = args
        self.risk = risk
        self.description = description

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold red]⚠ Tool Permission Required[/]", classes="dialog-title")
            yield Static(f"[dim]Tool:[/]  [bold]{self.tool}[/]")
            yield Static(f"[dim]Args:[/]  {self.args[:200]}")
            yield Static(f"[bold]Risk:[/] {self.risk}", id="risk")
            if self.description:
                yield Static(self.description, id="description")
            with Horizontal():
                yield Button("Allow (y)", id="allow", variant="success")
                yield Button("Deny (n)", id="deny", variant="error")
                yield Button("Always (a)", id="always")

    def action_allow(self) -> None:
        self.dismiss("allow")

    def action_deny(self) -> None:
        self.dismiss("deny")

    def action_always_allow(self) -> None:
        self.dismiss("always_allow")

    def action_dismiss_modal(self) -> None:
        # ESC = deny
        self.dismiss("deny")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        mapping = {"allow": "allow", "deny": "deny", "always": "always_allow"}
        self.dismiss(mapping.get(event.button.id or "", "deny"))
