"""Base modal class — common ESC handling + dialog styling."""

from __future__ import annotations

from textual.binding import Binding
from textual.screen import ModalScreen


class BaseModal(ModalScreen):
    """All app modals inherit from this for consistent ESC behaviour."""

    DEFAULT_CSS = """
    BaseModal {
        align: center middle;
    }
    BaseModal .dialog {
        background: $surface;
        border: round $primary;
        padding: 1 2;
        width: 60;
        height: auto;
        max-height: 90%;
    }
    BaseModal .dialog-title {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }
    BaseModal .dialog-hint {
        color: $text-muted;
        margin-top: 1;
        text-align: right;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close", show=False),
    ]

    def action_dismiss_modal(self) -> None:
        self.dismiss()
