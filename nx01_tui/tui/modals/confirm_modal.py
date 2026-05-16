"""ConfirmModal — generic y/n confirmation for destructive actions."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from .base import BaseModal


class ConfirmModal(BaseModal):
    """ModalScreen[bool] — returns True on confirm, False on cancel."""

    DEFAULT_CSS = """
    ConfirmModal .dialog { width: 50; }
    ConfirmModal Button { margin: 0 1; }
    """

    BINDINGS = [
        Binding("y", "confirm", "Confirm", show=False),
        Binding("n", "cancel", "Cancel", show=False),
    ]

    def __init__(self, prompt: str, dangerous: bool = False, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.prompt = prompt
        self.dangerous = dangerous

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(
                f"[bold {'red' if self.dangerous else 'yellow'}]Confirm[/]",
                classes="dialog-title",
            )
            yield Static(self.prompt)
            with Horizontal():
                yield Button(
                    "Yes (y)", id="yes", variant="success" if not self.dangerous else "error"
                )
                yield Button("No (n)", id="no")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")
