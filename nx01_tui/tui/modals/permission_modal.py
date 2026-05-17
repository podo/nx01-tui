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
    """Permission gate — chrome scales with `risk` per #29 item 4.

    low    → round $warning border, "Allow" focused, Always button visible
    medium → thick  $warning border, "Deny" focused, Always button visible
    high   → heavy  $error   border, "Deny" focused, Always button hidden
    """

    DEFAULT_CSS = """
    PermissionModal .dialog {
        width: 64;
        border: round $warning;
    }
    PermissionModal.risk-medium .dialog { border: thick $warning; }
    PermissionModal.risk-high   .dialog { border: heavy $error; }
    PermissionModal Button { margin: 0 1; }
    PermissionModal #risk { margin-bottom: 1; }
    PermissionModal.risk-low    #risk { color: $warning; }
    PermissionModal.risk-medium #risk { color: $warning; text-style: bold; }
    PermissionModal.risk-high   #risk { color: $error;   text-style: bold reverse; }
    PermissionModal #description {
        color: $text-muted;
        margin: 1 0;
    }
    PermissionModal #irreversible {
        color: $error;
        text-style: bold;
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
        self.risk = (risk or "low").lower()
        if self.risk not in ("low", "medium", "high"):
            self.risk = "low"
        self.description = description
        self.add_class(f"risk-{self.risk}")

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold red]Tool Permission Required[/]", classes="dialog-title")
            yield Static(f"[dim]Tool:[/]  [bold]{self.tool}[/]")
            yield Static(f"[dim]Args:[/]  {self.args[:200]}")
            yield Static(f"[bold]Risk:[/] {self.risk}", id="risk")
            if self.description:
                yield Static(self.description, id="description")
            if self.risk == "high":
                yield Static("This is not reversible.", id="irreversible")
            with Horizontal():
                # Risk-driven button order + focus: high/medium put Deny first.
                if self.risk == "low":
                    yield Button("Allow (y)", id="allow", variant="success")
                    yield Button("Deny (n)", id="deny", variant="error")
                    yield Button("Always (a)", id="always")
                elif self.risk == "medium":
                    yield Button("Deny (n)", id="deny", variant="error")
                    yield Button("Allow (y)", id="allow", variant="success")
                    yield Button("Always (a)", id="always")
                else:  # high — no "always" path
                    yield Button("Deny (n)", id="deny", variant="error")
                    yield Button("Allow (y)", id="allow", variant="warning")

    def on_mount(self) -> None:
        # Focus the safe button by default — Deny for medium+high, Allow for low.
        try:
            target = "#allow" if self.risk == "low" else "#deny"
            self.query_one(target, Button).focus()
        except Exception:  # noqa: BLE001
            pass

    def action_allow(self) -> None:
        self.dismiss("allow")

    def action_deny(self) -> None:
        self.dismiss("deny")

    def action_always_allow(self) -> None:
        # No always-allow path on high-risk tools — keyboard fallback to deny.
        if self.risk == "high":
            self.dismiss("deny")
            return
        self.dismiss("always_allow")

    def action_dismiss_modal(self) -> None:
        # ESC = deny
        self.dismiss("deny")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        mapping = {"allow": "allow", "deny": "deny", "always": "always_allow"}
        self.dismiss(mapping.get(event.button.id or "", "deny"))
