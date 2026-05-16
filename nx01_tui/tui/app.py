"""Nx01TuiApp — Textual operator cockpit for the NX01 fleet (#76)."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime

import httpx
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.events import Key, MouseScrollUp
from textual.widget import Widget
from textual.widgets import (
    Footer,
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


class FleetHeader(Static):
    """Titlebar: uptime + optional disconnect banner."""

    DEFAULT_CSS = """
    FleetHeader {
        height: 1;
        background: $primary-darken-3;
        color: $text;
        padding: 0 1;
    }
    FleetHeader.disconnected {
        background: $warning-darken-2;
        color: $warning;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._start: float = 0.0
        self._disconnected: bool = False
        self._reconnect_in: int = 0

    def on_mount(self) -> None:
        self._start = time.time()
        self.set_interval(1, self._tick)

    def _tick(self) -> None:
        self.refresh()

    def render(self) -> str:
        elapsed = int(time.time() - self._start)
        h, m = divmod(elapsed // 60, 60)
        uptime = f"{h}h {m:02d}m" if h else f"{m}m"
        if self._disconnected:
            return (
                f"NX01 Fleet   ⚠ disconnected — reconnecting in {self._reconnect_in}s…"
                f"   uptime {uptime}"
            )
        return f"NX01 Fleet                                                uptime {uptime}"

    def set_disconnected(self, countdown: int) -> None:
        self._disconnected = True
        self._reconnect_in = countdown
        self.add_class("disconnected")
        self.refresh()

    def set_connected(self) -> None:
        self._disconnected = False
        self.remove_class("disconnected")
        self.refresh()


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
    """

    def compose(self) -> ComposeResult:
        yield Label("TOOL CALLS", classes="sidebar-title")

    def add_tool(self, tool: str, arg: str, status: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        status_markup = {
            "started": "[yellow]⋯ running[/]",
            "in_progress": "[yellow]⋯ running[/]",
            "completed": "[green]✓ done[/]",
            "done": "[green]✓ done[/]",
            "error": "[red]✗ error[/]",
            "failed": "[red]✗ error[/]",
        }.get(status, f"[dim]{status}[/]")
        arg_short = (arg[:22] + "…") if len(arg) > 24 else arg
        markup = f"[dim]{ts}[/] [bold orange1]⚙ {tool}[/]\n[dim]{arg_short}[/]\n{status_markup}"
        self.mount(Label(markup, classes="tool-entry", markup=True))
        self.scroll_end(animate=False)

    def seal_turn(self) -> None:
        for child in self.query(".tool-entry"):
            child.add_class("tool-dim")
        self.mount(Label("── idle ──", classes="idle-sep"))
        self.scroll_end(animate=False)


class _ThinkingBlock(Vertical):
    """Inline thinking stream that can be faded once the agent turn completes."""

    DEFAULT_CSS = """
    _ThinkingBlock { height: auto; padding: 0 1; }
    _ThinkingBlock Label { color: #4a5a6a; text-style: italic; }
    _ThinkingBlock.faded Label { color: #2e3e4e; }
    """

    def add_line(self, text: str) -> None:
        self.mount(Label(f"~ {text}"))


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
    ConversationPane .new-content-badge {
        dock: bottom;
        background: $primary-darken-2;
        color: $text;
        height: 1;
        padding: 0 1;
        display: none;
    }
    ConversationPane .new-content-badge.visible {
        display: block;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._scroll_locked: bool = False
        self._active_thinking: _ThinkingBlock | None = None

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="conv-scroll"):
            yield RichLog(highlight=False, markup=True, auto_scroll=False, id="conv-log")
        yield Label(
            "↓ new content  (End to resume)",
            classes="new-content-badge",
            id="new-badge",
        )

    def _scroll(self) -> ScrollableContainer:
        return self.query_one("#conv-scroll", ScrollableContainer)

    def _log(self) -> RichLog:
        return self.query_one("#conv-log", RichLog)

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        """Engage scroll lock when user scrolls upward."""
        sc = self._scroll()
        if sc.scroll_y < sc.max_scroll_y:
            self._scroll_locked = True
            try:
                self.query_one("#new-badge").add_class("visible")
            except NoMatches:
                pass

    def append_user(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        self._log().write(f"[dim]{ts}[/]  [bold yellow]you[/]  {text}\n")
        self._maybe_scroll()

    def append_chunk(self, text: str) -> None:
        self._log().write(text, expand=False)
        self._maybe_scroll()

    def start_agent_turn(self, flavor: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        self._log().write(f"\n[dim]{ts}[/]  [bold green]{flavor}[/]  [dim yellow]● thinking…[/]\n")
        block = _ThinkingBlock()
        self._active_thinking = block
        self._scroll().mount(block)

    def append_thinking(self, text: str) -> None:
        if self._active_thinking is not None:
            self._active_thinking.add_line(text)
        self._maybe_scroll()

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
        self._scroll().scroll_end(animate=False)

    def _maybe_scroll(self) -> None:
        if self._scroll_locked:
            try:
                self.query_one("#new-badge").add_class("visible")
            except NoMatches:
                pass
        else:
            self._scroll().scroll_end(animate=False)


class CommandPalette(Widget):
    """Slash command autocomplete overlay shown above the input bar."""

    DEFAULT_CSS = """
    CommandPalette {
        dock: bottom;
        height: auto;
        max-height: 12;
        background: $surface;
        border: solid $primary-darken-2;
        display: none;
        margin-bottom: 3;
        margin-left: 1;
        margin-right: 1;
    }
    CommandPalette.visible {
        display: block;
    }
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


class Nx01TuiApp(App):
    """NX01 fleet operator cockpit."""

    BINDINGS = [
        Binding("end", "resume_scroll", "Resume scroll", show=False),
        Binding("escape", "handle_escape", "Esc", show=False),
        Binding("q", "quit_if_empty", "Quit", show=True),
    ]

    DEFAULT_CSS = """
    Screen {
        layout: vertical;
    }
    TabbedContent {
        height: 1fr;
    }
    TabPane {
        padding: 0;
    }
    #input-row {
        dock: bottom;
        height: 3;
        border-top: solid $primary-darken-3;
        background: $surface-darken-1;
        align: left middle;
        padding: 0 1;
        layer: 2;
    }
    #msg-input {
        width: 1fr;
    }
    #flavor-badge {
        width: auto;
        padding: 0 1;
        color: $primary;
    }
    #cmd-palette {
        dock: bottom;
        layer: 1;
    }
    """

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None):
        super().__init__()
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._states: dict[str, FlavorState] = {}
        self._esc_time: float = 0.0
        self._thinking_started: set[str] = set()
        self._pending_events: dict[str, list[dict]] = {}

    def compose(self) -> ComposeResult:
        yield FleetHeader(id="fleet-header")
        yield TabbedContent(id="tabs")
        with Horizontal(id="input-row"):
            yield Input(placeholder="send a message or /command…", id="msg-input")
            yield Label("— ▾", id="flavor-badge")
        yield CommandPalette(id="cmd-palette")

    def on_mount(self) -> None:
        self.run_worker(self._sse_worker(), exclusive=True, name="sse")
        self.query_one("#msg-input", Input).focus()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        self.query_one("#msg-input", Input).focus()
        if event.pane and event.pane.id:
            flavor = str(event.pane.id).removeprefix("tab-")
            self.query_one("#flavor-badge", Label).update(f"{flavor} ▾")

    def on_key(self, event: Key) -> None:
        palette = self.query_one("#cmd-palette", CommandPalette)
        if palette.is_open():
            return
        tabs = self.query_one("#tabs", TabbedContent)
        panes = list(tabs.query_one("ContentSwitcher").children)
        if not panes:
            return
        key_num = None
        if event.key == "ctrl+1":
            key_num = 0
        elif event.key == "ctrl+2":
            key_num = 1
        elif event.key == "ctrl+3":
            key_num = 2
        elif event.key == "ctrl+4":
            key_num = 3
        if key_num is not None and key_num < len(panes):
            tabs.active = panes[key_num].id

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
                        self.call_later(self.query_one("#fleet-header", FleetHeader).set_connected)
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
                self.call_later(
                    self.query_one("#fleet-header", FleetHeader).set_disconnected, countdown
                )
                await asyncio.sleep(1)
            backoff = min(backoff * 2, 30)

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
        """Dispatch a single event payload to the already-mounted flavor pane."""
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

    def _mount_flavor_tab(self, flavor: str) -> None:
        async def _do() -> None:
            tabs = self.query_one("#tabs", TabbedContent)
            pane = TabPane(flavor, id=f"tab-{flavor}")
            await tabs.add_pane(pane)
            row = Horizontal()
            conv = ConversationPane(id=f"conv-{flavor}")
            sidebar = ToolSidebar(id=f"tools-{flavor}")
            await pane.mount(row)
            await row.mount(conv, sidebar)
            badge = self.query_one("#flavor-badge", Label)
            badge.update(f"{flavor} ▾")
            for buffered in self._pending_events.pop(flavor, []):
                self._dispatch_to_pane(flavor, buffered)

        self.call_later(_do)

    def _update_tab_label(self, flavor: str, status: str) -> None:
        pass

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

    async def _send_message(self, text: str) -> None:
        tabs = self.query_one("#tabs", TabbedContent)
        active_id = tabs.active
        if not active_id:
            return
        flavor = str(active_id).removeprefix("tab-")

        try:
            conv = self.query_one(f"#conv-{flavor}", ConversationPane)
            conv.append_user(text)
        except NoMatches:
            pass

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        body = json.dumps({"target_flavor": flavor, "message": text}).encode()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"{self._base_url}/message", content=body, headers=headers)
        except Exception:
            pass

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
        inp = self.query_one("#msg-input", Input)
        if not inp.value:
            self.exit()
