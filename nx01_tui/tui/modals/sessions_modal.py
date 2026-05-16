"""SessionsModal — list sessions grouped by flavor with r/f/e/d actions."""

from __future__ import annotations

from dataclasses import dataclass, field

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from .base import BaseModal


@dataclass
class SessionEntry:
    session_id: str
    flavor: str
    title: str = "Untitled"
    last_active: str = ""
    message_count: int = 0
    preview: str = ""


@dataclass
class SessionAction:
    action: str  # resume | fork | rename | delete | new
    session_id: str = ""
    flavor: str = ""
    payload: dict = field(default_factory=dict)


class SessionsModal(BaseModal):
    """ModalScreen[SessionAction|None]."""

    DEFAULT_CSS = """
    SessionsModal .dialog { width: 80; height: 90%; }
    SessionsModal Input { margin-bottom: 1; }
    SessionsModal OptionList { height: 1fr; }
    """

    BINDINGS = [
        Binding("r", "resume", "Resume", show=True),
        Binding("f", "fork", "Fork", show=True),
        Binding("e", "rename", "Rename", show=True),
        Binding("d", "delete", "Delete", show=True),
        Binding("n", "new_session", "New", show=True),
    ]

    def __init__(self, sessions: list[SessionEntry], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.sessions = sessions
        self._visible_ids: list[tuple[str, str]] = []  # (session_id, flavor)

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("[bold]Sessions[/]", classes="dialog-title")
            yield Input(placeholder="Filter sessions…", id="filter")
            yield OptionList(*self._render_options(""), id="session-list")
            yield Static(
                "[dim]r resume · f fork · e rename · d delete · n new · ESC close[/]",
                classes="dialog-hint",
            )

    def _render_options(self, query: str) -> list[Option]:
        q = query.lower().strip()
        # Group by flavor
        by_flavor: dict[str, list[SessionEntry]] = {}
        for s in self.sessions:
            if q and q not in f"{s.title} {s.preview}".lower():
                continue
            by_flavor.setdefault(s.flavor, []).append(s)

        opts: list[Option] = []
        self._visible_ids = []
        if not by_flavor:
            opts.append(Option("[dim]no sessions[/]", disabled=True))
            return opts
        for flavor in sorted(by_flavor):
            opts.append(Option(f"[dim]── {flavor} ──[/]", disabled=True))
            for s in by_flavor[flavor]:
                label = (
                    f"[bold]{s.title}[/]  "
                    f"[dim]{s.last_active} · {s.message_count} msgs[/]\n"
                    f"  [dim]{s.preview[:60]}[/]"
                )
                opts.append(Option(label, id=f"{flavor}::{s.session_id}"))
                self._visible_ids.append((s.session_id, flavor))
        return opts

    def _selected(self) -> tuple[str, str] | None:
        try:
            lst = self.query_one("#session-list", OptionList)
            opt = lst.get_option_at_index(lst.highlighted or 0)
            if opt and opt.id and "::" in opt.id:
                flavor, sid = opt.id.split("::", 1)
                return (sid, flavor)
        except Exception:  # noqa: BLE001
            pass
        return None

    def on_input_changed(self, event: Input.Changed) -> None:
        try:
            lst = self.query_one("#session-list", OptionList)
            lst.clear_options()
            for opt in self._render_options(event.value):
                lst.add_option(opt)
        except Exception:  # noqa: BLE001
            pass

    def action_resume(self) -> None:
        sel = self._selected()
        if sel:
            self.dismiss(SessionAction("resume", session_id=sel[0], flavor=sel[1]))

    def action_fork(self) -> None:
        sel = self._selected()
        if sel:
            self.dismiss(SessionAction("fork", session_id=sel[0], flavor=sel[1]))

    def action_rename(self) -> None:
        sel = self._selected()
        if sel:
            self.dismiss(SessionAction("rename", session_id=sel[0], flavor=sel[1]))

    def action_delete(self) -> None:
        sel = self._selected()
        if sel:
            self.dismiss(SessionAction("delete", session_id=sel[0], flavor=sel[1]))

    def action_new_session(self) -> None:
        self.dismiss(SessionAction("new"))
