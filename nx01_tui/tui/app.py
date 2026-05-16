"""Nx01TuiApp — Textual operator cockpit for the NX01 fleet (#76)."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from urllib.parse import urlparse

import httpx
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.events import MouseScrollUp
from textual.widget import Widget
from textual.widgets import (
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from nx01_tui.tui.commands import filter_commands
from nx01_tui.tui.state import FlavorState, route_event

_STATUS_DOT = {
    "running": "[bold green]●[/]",
    "idle": "[dim yellow]◌[/]",
    "offline": "[dim]·[/]",
    "crashed": "[bold red]✗[/]",
    "stopped": "[dim]·[/]",
}


def _dot(status: str) -> str:
    return _STATUS_DOT.get(status, "[dim]?[/]")


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or url
    except Exception:
        return url


# ─── Header ───────────────────────────────────────────────────────────────────


class FleetHeader(Horizontal):
    """Titlebar split into left (status) and right (host + uptime)."""

    DEFAULT_CSS = """
    FleetHeader {
        height: 1;
        background: $primary-darken-3;
        color: $text;
    }
    FleetHeader #hdr-left {
        width: 1fr;
        padding: 0 1;
    }
    FleetHeader #hdr-right {
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }
    FleetHeader.disconnected {
        background: $warning-darken-2;
        color: $warning;
    }
    """

    def __init__(self, host: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._host = host
        self._start = time.time()
        self._disconnected = False
        self._reconnect_in = 0
        self._flavor_count = 0
        self._flavor_statuses: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Static("", id="hdr-left")
        yield Static("", id="hdr-right")

    def on_mount(self) -> None:
        self.set_interval(1, self._tick)
        self._render_both()

    def _tick(self) -> None:
        self._render_both()

    def _render_both(self) -> None:
        elapsed = int(time.time() - self._start)
        h, m = divmod(elapsed // 60, 60)
        uptime = f"{h}h {m:02d}m" if h else f"{m}m"

        if self._disconnected:
            left = f"[bold red]✗[/] disconnected — reconnecting in {self._reconnect_in}s…"
        else:
            dots = (
                "  ".join(f"{_dot(s)} {n}" for n, s in self._flavor_statuses.items())
                if self._flavor_statuses
                else ""
            )
            count = f"  {dots}" if dots else ""
            left = f"[bold green]●[/] NX01 Fleet{count}"

        right = f"{self._host}  uptime {uptime}"

        try:
            self.query_one("#hdr-left", Static).update(left)
            self.query_one("#hdr-right", Static).update(right)
        except NoMatches:
            pass

    def update_flavor(self, name: str, status: str) -> None:
        self._flavor_statuses[name] = status
        self._flavor_count = len(self._flavor_statuses)
        self._render_both()

    def set_disconnected(self, countdown: int) -> None:
        self._disconnected = True
        self._reconnect_in = countdown
        self.add_class("disconnected")
        self._render_both()

    def set_connected(self) -> None:
        self._disconnected = False
        self.remove_class("disconnected")
        self._render_both()


# ─── Key hints bar (replaces Footer) ──────────────────────────────────────────


class KeyHints(Static):
    """One-line keybinding strip docked at the very bottom."""

    DEFAULT_CSS = """
    KeyHints {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text-muted;
        padding: 0 1;
    }
    """

    HINTS = (
        "[dim]ctrl+1-4[/] tabs  "
        "[dim]esc[/] clear  "
        "[dim]esc×2[/] stop  "
        "[dim]q[/] quit  "
        "[dim]@flavor[/] route"
    )

    def render(self) -> str:
        return self.HINTS


# ─── Global empty state ────────────────────────────────────────────────────────


class EmptyState(Static):
    """Shown when no flavor tabs exist yet."""

    DEFAULT_CSS = """
    EmptyState {
        height: 1fr;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
        text-style: italic;
    }
    EmptyState.hidden {
        display: none;
    }
    """

    def __init__(self, host: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._host = host
        self._flavors: list[str] = []
        self._connecting = True

    def set_connecting(self, host: str) -> None:
        self._connecting = True
        self._refresh_text()

    def set_flavors(self, flavors: list[str]) -> None:
        self._connecting = False
        self._flavors = flavors
        self._refresh_text()

    def _refresh_text(self) -> None:
        if self._connecting:
            text = f"Connecting to {self._host}…"
        elif not self._flavors:
            text = f"Connected · no flavors found on {self._host}"
        else:
            flavor_list = "  ".join(f"[bold]{f}[/]" for f in self._flavors)
            text = (
                f"Connected to {self._host}\n\n"
                f"Available flavors:  {flavor_list}\n\n"
                "[dim]Send a message — or type [/][bold]@assistant hello[/]"
                "[dim] to target a flavor[/]"
            )
        self.update(text)


# ─── Tool sidebar ──────────────────────────────────────────────────────────────


class ToolSidebar(ScrollableContainer):
    """Scrollable tool call log for one flavor tab."""

    DEFAULT_CSS = """
    ToolSidebar {
        width: 30%;
        border-left: solid $primary-darken-3;
        background: $surface-darken-1;
    }
    ToolSidebar .sidebar-title {
        background: $primary-darken-3;
        color: $text-muted;
        text-style: bold;
        padding: 0 1;
        height: 1;
    }
    ToolSidebar .tool-entry {
        padding: 0 1;
        height: auto;
    }
    ToolSidebar .tool-dim {
        color: $text-disabled;
    }
    ToolSidebar .idle-sep {
        color: $text-disabled;
        padding: 0 1;
    }
    ToolSidebar .empty-hint {
        color: $text-disabled;
        text-style: italic;
        padding: 1 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("TOOL CALLS", classes="sidebar-title")
        yield Label("no tool calls yet", classes="empty-hint", id="tools-empty")

    def add_tool(self, tool: str, arg: str, status: str) -> None:
        try:
            self.query_one("#tools-empty").remove()
        except NoMatches:
            pass
        ts = datetime.now().strftime("%H:%M")
        status_markup = {
            "started": "[yellow]⋯[/]",
            "in_progress": "[yellow]⋯[/]",
            "completed": "[green]✓[/]",
            "done": "[green]✓[/]",
            "error": "[red]✗[/]",
            "failed": "[red]✗[/]",
        }.get(status, f"[dim]{status}[/]")
        arg_short = (arg[:22] + "…") if len(arg) > 24 else arg
        markup = f"[dim]{ts}[/] [bold orange1]⚙ {tool}[/]\n[dim]{arg_short}[/] {status_markup}"
        self.mount(Label(markup, classes="tool-entry", markup=True))
        self.scroll_end(animate=False)

    def seal_turn(self) -> None:
        for child in self.query(".tool-entry"):
            child.add_class("tool-dim")
        self.mount(Label("── idle ──", classes="idle-sep"))
        self.scroll_end(animate=False)


# ─── Thinking block ────────────────────────────────────────────────────────────


class _ThinkingBlock(Vertical):
    DEFAULT_CSS = """
    _ThinkingBlock { height: auto; padding: 0 1; }
    _ThinkingBlock Label { color: #4a5a6a; text-style: italic; }
    _ThinkingBlock.faded Label { color: #2e3e4e; }
    """

    def add_line(self, text: str) -> None:
        self.mount(Label(f"~ {text}"))


# ─── Conversation pane ─────────────────────────────────────────────────────────


class ConversationPane(Vertical):
    """Scrollable conversation with inline thinking stream."""

    DEFAULT_CSS = """
    ConversationPane {
        width: 70%;
    }
    ConversationPane #conv-scroll {
        height: 1fr;
    }
    ConversationPane RichLog {
        border: none;
        padding: 0 1;
        scrollbar-size: 1 1;
        height: auto;
    }
    ConversationPane .conv-empty {
        color: $text-disabled;
        text-style: italic;
        padding: 1 2;
    }
    ConversationPane .new-badge {
        dock: bottom;
        background: $primary-darken-2;
        color: $text;
        height: 1;
        padding: 0 1;
        display: none;
    }
    ConversationPane .new-badge.visible {
        display: block;
    }
    """

    def __init__(self, flavor: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._flavor = flavor
        self._scroll_locked = False
        self._active_thinking: _ThinkingBlock | None = None
        self._has_content = False

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="conv-scroll"):
            yield RichLog(highlight=False, markup=True, auto_scroll=False)
        yield Label(
            f"No messages yet — type below to chat with [bold]{self._flavor or 'a flavor'}[/]",
            classes="conv-empty",
            id="conv-empty",
            markup=True,
        )
        yield Label("↓ new content  (End to resume)", classes="new-badge", id="new-badge")

    def _clear_empty(self) -> None:
        if not self._has_content:
            self._has_content = True
            try:
                self.query_one("#conv-empty").remove()
            except NoMatches:
                pass

    def _sc(self) -> ScrollableContainer:
        return self.query_one("#conv-scroll", ScrollableContainer)

    def _log(self) -> RichLog:
        return self.query_one("RichLog")

    def on_mouse_scroll_up(self, _: MouseScrollUp) -> None:
        sc = self._sc()
        if sc.scroll_y < sc.max_scroll_y:
            self._scroll_locked = True
            try:
                self.query_one("#new-badge").add_class("visible")
            except NoMatches:
                pass

    def append_user(self, text: str) -> None:
        self._clear_empty()
        ts = datetime.now().strftime("%H:%M")
        self._log().write(f"[dim]{ts}[/]  [bold yellow]you[/]  {text}\n")
        self._scroll()

    def append_chunk(self, text: str) -> None:
        self._clear_empty()
        self._log().write(text, expand=False)
        self._scroll()

    def start_agent_turn(self, flavor: str) -> None:
        self._clear_empty()
        ts = datetime.now().strftime("%H:%M")
        self._log().write(f"\n[dim]{ts}[/]  [bold green]{flavor}[/]  [dim yellow]● thinking…[/]\n")
        block = _ThinkingBlock()
        self._active_thinking = block
        self._sc().mount(block)

    def append_thinking(self, text: str) -> None:
        if self._active_thinking is not None:
            self._active_thinking.add_line(text)
        self._scroll()

    def seal_turn(self) -> None:
        if self._active_thinking is not None:
            self._active_thinking.add_class("faded")
            self._active_thinking = None
        self._log().write("\n")

    def resume_scroll(self) -> None:
        self._scroll_locked = False
        try:
            self.query_one("#new-badge").remove_class("visible")
        except NoMatches:
            pass
        self._sc().scroll_end(animate=False)

    def _scroll(self) -> None:
        if self._scroll_locked:
            try:
                self.query_one("#new-badge").add_class("visible")
            except NoMatches:
                pass
        else:
            self._sc().scroll_end(animate=False)


# ─── Command palette ───────────────────────────────────────────────────────────


class CommandPalette(Widget):
    """Slash command autocomplete overlay above the input bar."""

    DEFAULT_CSS = """
    CommandPalette {
        dock: bottom;
        height: auto;
        max-height: 12;
        background: $surface;
        border: solid $primary-darken-2;
        display: none;
        margin-bottom: 4;
        margin-left: 1;
        margin-right: 1;
    }
    CommandPalette.visible { display: block; }
    CommandPalette ListView {
        height: auto;
        max-height: 12;
        background: $surface;
    }
    """

    _current_prefix: str = ""

    def compose(self) -> ComposeResult:
        yield ListView(id="palette-list")

    def show(self, prefix: str) -> None:
        self._current_prefix = prefix
        matches = filter_commands(prefix)
        lv = self.query_one("#palette-list", ListView)
        lv.clear()
        for cmd in matches[:12]:
            markup = f"[bold]{cmd['command']}[/]  [dim]{cmd['category']} · {cmd['description']}[/]"
            lv.append(ListItem(Label(markup, markup=True)))
        self.add_class("visible")

    def hide(self) -> None:
        self.remove_class("visible")

    def is_open(self) -> bool:
        return "visible" in self.classes

    def highlighted_command(self) -> str | None:
        lv = self.query_one("#palette-list", ListView)
        idx = lv.index
        matches = filter_commands(self._current_prefix)
        if idx is not None and idx < len(matches):
            return matches[idx]["command"]
        return None


# ─── Main app ──────────────────────────────────────────────────────────────────


class Nx01TuiApp(App):
    """NX01 fleet operator cockpit."""

    BINDINGS = [
        Binding("ctrl+1", "switch_tab(0)", "Tab 1", show=False),
        Binding("ctrl+2", "switch_tab(1)", "Tab 2", show=False),
        Binding("ctrl+3", "switch_tab(2)", "Tab 3", show=False),
        Binding("ctrl+4", "switch_tab(3)", "Tab 4", show=False),
        Binding("ctrl+end", "resume_scroll", "Resume scroll", show=False),
        Binding("escape", "handle_escape", "Esc", show=False),
        Binding("q", "quit_if_empty", "Quit", show=True),
    ]

    DEFAULT_CSS = """
    Screen { layout: vertical; }

    TabbedContent {
        height: 1fr;
        display: none;
    }
    TabbedContent.visible {
        display: block;
    }
    TabPane { padding: 0; }

    #input-row {
        dock: bottom;
        height: 3;
        border-top: solid $primary-darken-3;
        background: $surface-darken-1;
        align: left middle;
        padding: 0 1;
        layer: 2;
    }
    #msg-input { width: 1fr; }
    #flavor-badge {
        width: auto;
        padding: 0 1;
        color: $primary;
    }
    #cmd-palette {
        dock: bottom;
        layer: 3;
    }
    """

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None):
        super().__init__()
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._host = _host(base_url)
        self._states: dict[str, FlavorState] = {}
        self._esc_time: float = 0.0
        self._thinking_started: set[str] = set()
        self._pending_events: dict[str, list[dict]] = {}
        self._first_tab_mounted = False

    def compose(self) -> ComposeResult:
        yield FleetHeader(host=self._host, id="fleet-header")
        yield EmptyState(host=self._host, id="empty-state")
        yield TabbedContent(id="tabs")
        with Horizontal(id="input-row"):
            yield Input(placeholder="message / @flavor / /command…", id="msg-input")
            yield Label("select flavor ▾", id="flavor-badge")
        yield CommandPalette(id="cmd-palette")
        yield KeyHints()

    def on_mount(self) -> None:
        self.run_worker(self._prefetch_flavors(), exclusive=False, name="prefetch")
        self.run_worker(self._sse_worker(), exclusive=True, name="sse")
        self.query_one("#msg-input", Input).focus()

    # ── Pre-fetch ──────────────────────────────────────────────────────────────

    async def _prefetch_flavors(self) -> None:
        es = self.query_one("#empty-state", EmptyState)
        es.set_connecting(self._host)

        url = f"{self._base_url}/health"
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url, headers=headers)
                data = resp.json()
                flavors: dict = data.get("flavors", {})
                self.call_later(es.set_flavors, list(flavors.keys()))
                for name, info in flavors.items():
                    if name not in self._states:
                        status = info.get("status", "idle") if isinstance(info, dict) else "idle"
                        self._states[name] = FlavorState(name=name, status=status)
                        self._pending_events.setdefault(name, [])
                        self.call_later(self._mount_flavor_tab, name)
        except Exception:
            self.call_later(es.set_flavors, [])

    # ── SSE worker ─────────────────────────────────────────────────────────────

    async def _sse_worker(self) -> None:
        url = f"{self._base_url}/events"
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        backoff = 1
        while True:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("GET", url, headers=headers) as resp:
                        resp.raise_for_status()
                        backoff = 1
                        try:
                            header = self.query_one("#fleet-header", FleetHeader)
                            self.call_later(header.set_connected)
                        except NoMatches:
                            pass
                        _event_type = ""
                        data_lines: list[str] = []
                        async for line in resp.aiter_lines():
                            if line.startswith("event:"):
                                _event_type = line[6:].strip()
                            elif line.startswith("data:"):
                                data_lines.append(line[5:].strip())
                            elif not line or line.startswith(":"):
                                if data_lines:
                                    raw = "\n".join(data_lines)
                                    try:
                                        payload = json.loads(raw)
                                    except json.JSONDecodeError:
                                        pass
                                    else:
                                        self.call_later(self._handle_event, payload)
                                _event_type = ""
                                data_lines = []
            except Exception:
                pass

            for countdown in range(backoff, 0, -1):
                try:
                    self.call_later(
                        self.query_one("#fleet-header", FleetHeader).set_disconnected, countdown
                    )
                except NoMatches:
                    pass
                await asyncio.sleep(1)
            backoff = min(backoff * 2, 30)

    # ── Event dispatch ─────────────────────────────────────────────────────────

    def _handle_event(self, payload: dict) -> None:
        flavor = payload.get("flavor", "")
        if not flavor:
            return
        if flavor not in self._states:
            self._states[flavor] = FlavorState(name=flavor)
            self._pending_events.setdefault(flavor, [])
            self._mount_flavor_tab(flavor)

        state = self._states[flavor]
        route_event(state, payload)

        try:
            self.query_one(f"#conv-{flavor}", ConversationPane)
        except NoMatches:
            self._pending_events.setdefault(flavor, []).append(payload)
            return

        self._dispatch_to_pane(flavor, payload)

    def _dispatch_to_pane(self, flavor: str, payload: dict) -> None:
        try:
            conv = self.query_one(f"#conv-{flavor}", ConversationPane)
            sidebar = self.query_one(f"#tools-{flavor}", ToolSidebar)
        except NoMatches:
            return

        kind = payload.get("type", "")
        if kind == "AgentChunkEvent":
            conv.append_chunk(payload.get("text", ""))
        elif kind == "AgentThinkingEvent":
            if flavor not in self._thinking_started:
                self._thinking_started.add(flavor)
                conv.start_agent_turn(flavor)
            conv.append_thinking(payload.get("text", ""))
        elif kind == "AgentTurnDoneEvent":
            self._thinking_started.discard(flavor)
            conv.seal_turn()
            sidebar.seal_turn()
        elif kind == "ToolCallEvent":
            sidebar.add_tool(
                payload.get("tool", "?"),
                payload.get("title") or "",
                payload.get("status", ""),
            )
        elif kind == "FlavorStatusEvent":
            state = self._states[flavor]
            self._update_tab_label(flavor, state.status)
            self.query_one("#fleet-header", FleetHeader).update_flavor(flavor, state.status)

    # ── Tab management ─────────────────────────────────────────────────────────

    def _mount_flavor_tab(self, flavor: str) -> None:
        async def _do() -> None:
            tabs = self.query_one("#tabs", TabbedContent)
            status = self._states.get(flavor, FlavorState(name=flavor)).status
            label = f"{_dot(status)} {flavor}"
            pane = TabPane(label, id=f"tab-{flavor}")
            await tabs.add_pane(pane)

            row = Horizontal()
            conv = ConversationPane(flavor=flavor, id=f"conv-{flavor}")
            sidebar = ToolSidebar(id=f"tools-{flavor}")
            await pane.mount(row)
            await row.mount(conv, sidebar)

            # Show tabs, hide empty state on first tab
            if not self._first_tab_mounted:
                self._first_tab_mounted = True
                tabs.add_class("visible")
                try:
                    self.query_one("#empty-state").add_class("hidden")
                except NoMatches:
                    pass
                tabs.active = f"tab-{flavor}"

            # Update header
            self.query_one("#fleet-header", FleetHeader).update_flavor(flavor, status)

            # Flush buffered events
            for ev in self._pending_events.pop(flavor, []):
                self._dispatch_to_pane(flavor, ev)

        self.call_later(_do)

    def _update_tab_label(self, flavor: str, status: str) -> None:
        try:
            tab = self.query_one("#tabs", TabbedContent).get_tab(f"tab-{flavor}")
            tab.label = f"{_dot(status)} {flavor}"
        except (NoMatches, Exception):
            pass

    # ── Tab switching ──────────────────────────────────────────────────────────

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        self.query_one("#msg-input", Input).focus()
        if event.pane and event.pane.id:
            flavor = str(event.pane.id).removeprefix("tab-")
            status = self._states.get(flavor, FlavorState(name=flavor)).status
            self.query_one("#flavor-badge", Label).update(f"{_dot(status)} {flavor} ▾")

    def action_switch_tab(self, index: int) -> None:
        try:
            tabs = self.query_one("#tabs", TabbedContent)
            panes = list(tabs.query_one("ContentSwitcher").children)
            if index < len(panes):
                tabs.active = panes[index].id
        except NoMatches:
            pass

    # ── Input ──────────────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        palette = self.query_one("#cmd-palette", CommandPalette)
        if event.value.startswith("/"):
            palette.show(event.value)
        else:
            palette.hide()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        palette = self.query_one("#cmd-palette", CommandPalette)
        inp = self.query_one("#msg-input", Input)
        text = event.value.strip()

        if palette.is_open():
            selected = palette.highlighted_command()
            palette.hide()
            if selected:
                inp.value = selected + " "
                inp.focus()
            return

        if not text:
            return
        inp.clear()
        await self._send_message(text)

    def _resolve_flavor(self, text: str) -> tuple[str, str]:
        """Parse optional @flavor prefix → (flavor, message)."""
        if text.startswith("@"):
            parts = text[1:].split(" ", 1)
            if len(parts) == 2 and parts[0] in self._states:
                return parts[0], parts[1].strip()
        return "", text

    async def _send_message(self, text: str) -> None:
        at_flavor, message = self._resolve_flavor(text)

        tabs = self.query_one("#tabs", TabbedContent)
        active_id = tabs.active

        if at_flavor:
            flavor = at_flavor
            tabs.active = f"tab-{flavor}"
        elif active_id:
            flavor = str(active_id).removeprefix("tab-")
        elif self._states:
            flavor = next(iter(self._states))
            tabs.active = f"tab-{flavor}"
        else:
            return

        try:
            self.query_one(f"#conv-{flavor}", ConversationPane).append_user(message)
        except NoMatches:
            pass

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        body = json.dumps({"target_flavor": flavor, "message": message}).encode()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"{self._base_url}/message", content=body, headers=headers)
        except Exception:
            pass

    # ── Actions ────────────────────────────────────────────────────────────────

    def action_resume_scroll(self) -> None:
        tabs = self.query_one("#tabs", TabbedContent)
        active_id = tabs.active
        if not active_id:
            return
        flavor = str(active_id).removeprefix("tab-")
        try:
            self.query_one(f"#conv-{flavor}", ConversationPane).resume_scroll()
        except NoMatches:
            pass

    def action_handle_escape(self) -> None:
        palette = self.query_one("#cmd-palette", CommandPalette)
        if palette.is_open():
            palette.hide()
            return
        now = time.time()
        if now - self._esc_time < 0.5:
            self.run_worker(self._send_message("/stop"), name="stop-send")
        else:
            self._esc_time = now
            self.query_one("#msg-input", Input).clear()

    def action_quit_if_empty(self) -> None:
        if not self.query_one("#msg-input", Input).value:
            self.exit()
