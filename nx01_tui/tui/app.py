"""Nx01App — the main Textual application.

Composes:
  - AppHeader (top)
  - TabbedContent of FlavorPane per discovered flavor
  - StatusBar (bottom)
  - Footer (bottom)

Owns:
  - FlavorState per flavor
  - SSE worker (httpx streaming with reconnect)
  - Modal routing
  - Keybinding handlers
"""

from __future__ import annotations

import asyncio
import atexit
import datetime
import json
import logging
import re
import time
from contextlib import nullcontext
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

import httpx
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import TabbedContent, TabPane

from .client import ConnectionConfig, Nx01Client, stream_with_backoff
from .events import (
    AgentChunkEvent,
    AgentThinkingEvent,
    AgentTurnDoneEvent,
    FlavorStatusEvent,
    PermissionRequiredEvent,
    SkillLoadedEvent,
    SseEvent,
    ToolCallEvent,
)
from .modals import (
    CommandModal,
    ConfigModal,
    ConfirmModal,
    CostModal,
    DebugModal,
    HelpModal,
    MemoryModal,
    ModelPickerModal,
    PermissionModal,
    SessionAction,
    SessionEntry,
    SessionsModal,
    SkillsModal,
    ToolsModal,
    default_commands,
)
from .state import AgentState, FlavorState, route_event
from .widgets import (
    AppHeader,
    ChatInput,
    FilePickerDropdown,
    FlavorPane,
    SearchBar,
    SlashDropdown,
    StatusBar,
)

logger = logging.getLogger(__name__)

_STATE_FILE = Path.home() / ".nx01_tui_state.json"
_CALL_ID_RE = re.compile(r"^tc-[a-f0-9]{8,}$")


class ConnectionStatusMessage(Message):
    def __init__(self, kind: str, detail: str | object = "") -> None:
        super().__init__()
        self.kind = kind  # connected | disconnected | reconnecting
        self.detail = detail


class Nx01App(App):
    """Tabbed multi-flavor cockpit for nx01."""

    CSS_PATH = "app.tcss"

    BINDINGS = [
        # All app-level shortcuts use priority=True so TextArea/Input defaults
        # in the focused ChatInput don't swallow them (#29 QA N1 / N2).
        Binding("ctrl+p", "command_palette", "Commands", show=True, priority=True),
        Binding("ctrl+s", "open_sessions", "Sessions", show=True, priority=True),
        Binding("ctrl+m", "open_memory", "Memory", show=True, priority=True),
        Binding("ctrl+k", "open_skills", "Skills", show=False, priority=True),
        Binding("ctrl+t", "open_tools", "Tools", show=False, priority=True),
        Binding("ctrl+n", "new_session", "New", show=False, priority=True),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=True, priority=True),
        Binding("ctrl+f", "search", "Search", show=True, priority=True),
        Binding("ctrl+c", "stop_generation", "Stop", show=True, priority=True),
        Binding("question_mark", "help", "Help", show=True),
        Binding("ctrl+q", "request_quit", "Quit", show=True, priority=True),
        Binding("d", "toggle_dark", "Theme", show=False),
        Binding("ctrl+shift+d", "open_debug", "Debug", show=False, priority=True),
        # Yank moved to ctrl+y / ctrl+shift+y (priority) so TextArea doesn't
        # treat plain y/Y as typed characters (QA N2). Plain y/Y dropped.
        Binding("ctrl+y", "yank_focused", "Copy", show=False, priority=True),
        Binding("ctrl+shift+y", "yank_last_code", "Copy last", show=False, priority=True),
        # Flavor switching — priority so TextArea's Tab handling doesn't
        # swallow it when ChatInput is focused. (W3 of #26)
        Binding("tab", "switch_flavor", "Next flavor", show=True, priority=True),
        Binding("ctrl+1", "select_flavor(0)", show=False, priority=True),
        Binding("ctrl+2", "select_flavor(1)", show=False, priority=True),
        Binding("ctrl+3", "select_flavor(2)", show=False, priority=True),
        Binding("ctrl+4", "select_flavor(3)", show=False, priority=True),
        Binding("ctrl+5", "select_flavor(4)", show=False, priority=True),
        Binding("ctrl+6", "select_flavor(5)", show=False, priority=True),
        Binding("ctrl+7", "select_flavor(6)", show=False, priority=True),
        Binding("ctrl+8", "select_flavor(7)", show=False, priority=True),
        Binding("ctrl+9", "select_flavor(8)", show=False, priority=True),
    ]

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        flavors: list[str] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.base_url = base_url
        self.api_key = api_key
        self.config = ConnectionConfig(base_url=base_url, api_key=api_key)
        self.client = Nx01Client(self.config)
        self._states: dict[str, FlavorState] = {}
        self._panes: dict[str, FlavorPane] = {}
        self._initial_flavors = flavors or []
        self._connected = False
        # Per-flavor active session — set after resume so the next /message
        # post appends to that session instead of starting a new one (W7).
        self._active_session_id: dict[str, str] = {}
        self._current_correlation_id: str | None = None
        self._always_allow_tools: set[str] = set()
        # Rolling SSE event log — fed to DebugModal on demand.
        self._debug_buffer: deque[SseEvent] = deque(maxlen=500)
        self._debug_modal: DebugModal | None = None
        self._event_queue: asyncio.Queue[SseEvent] = asyncio.Queue()

    # ── Composition ──────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield AppHeader(id="app-header")
        yield TabbedContent(id="flavor-tabs")
        yield StatusBar(id="status-bar")

    async def on_mount(self) -> None:
        domain = urlparse(self.base_url).netloc or self.base_url
        self.query_one(AppHeader).domain = domain
        atexit.register(self._save_session_state)
        self.run_worker(self._bootstrap(), exclusive=True, name="bootstrap")
        self.set_interval(1 / 60, self._drain_events)   # 60fps drain

    async def on_unmount(self) -> None:
        self._save_session_state()
        await self.client.close()

    # ── Bootstrap (flavor discovery → SSE worker) ────────────────────

    async def _bootstrap(self) -> None:
        flavors: list[str] = list(self._initial_flavors)
        try:
            snapshot = await self.client.get_flavors()
            if isinstance(snapshot, dict):
                flavors = list(snapshot.keys())
            elif isinstance(snapshot, list):
                flavors = [f.get("name", "") for f in snapshot if isinstance(f, dict)]
            hdr = self.query_one(AppHeader)
            hdr.connected = True
            self._connected = True
            # Auto-pick the first available model so the header isn't blank
            # in the steady state (#29 item 18).
            picked = self._pick_first_model(snapshot)
            if picked:
                hdr.model = picked
        except httpx.HTTPStatusError as exc:
            # 401 / 403 are auth problems — distinguish from "server down".
            if exc.response.status_code in (401, 403):
                logger.warning("auth failed: %s", exc)
                hdr = self.query_one(AppHeader)
                hdr.connected = False
                hdr.auth_failed = True
                self.notify(
                    "Authentication failed (401). Check --api-key — it may be wrong or truncated.",
                    severity="error",
                    timeout=8,
                )
            else:
                logger.warning("flavor discovery failed: %s", exc)
                self.notify(f"Discovery failed: {exc}", severity="warning")
            if not flavors:
                flavors = ["assistant", "operator"]
        except httpx.HTTPError as exc:
            logger.warning("flavor discovery failed: %s", exc)
            self.notify(f"Could not discover flavors: {exc}", severity="warning")
            if not flavors:
                flavors = ["assistant", "operator"]

        for name in flavors:
            self._ensure_flavor(name)

        # Auto-focus the active flavor's input so the user can type immediately.
        self._focus_active_input()

        # Bootstrap each flavor's SlashDropdown with live commands + skills +
        # tools so `/` autocomplete surfaces everything the backend knows.
        await self._bootstrap_slash_dropdowns(flavors)
        await self._auto_resume_from_saved_state()

        self.run_worker(self._sse_loop(), exclusive=True, name="sse", group="net")

    @staticmethod
    def _pick_first_model(snapshot) -> str:
        """Extract the first non-empty `model` from a get_flavors() result.

        Tolerates both shapes — dict[str, dict] and list[dict].
        """
        items: list[dict] = []
        if isinstance(snapshot, dict):
            items = list(snapshot.values())
        elif isinstance(snapshot, list):
            items = [f for f in snapshot if isinstance(f, dict)]
        for f in items:
            m = (f or {}).get("model")
            if isinstance(m, str) and m:
                return m
        return ""

    async def _bootstrap_slash_dropdowns(self, flavors: list[str]) -> None:
        """Fetch commands once + per-flavor skills/tools; feed each dropdown.

        FlavorPane mounts are queued by `tabs.add_pane` (sync) but the actual
        DOM insertion happens on the next refresh cycle, so we yield once to
        let those mounts complete before querying the dropdowns.
        """
        # FlavorPane mounts queued by `tabs.add_pane` settle after a refresh.
        # Wait briefly so #slash-{flavor} is queryable.
        for _ in range(20):
            await asyncio.sleep(0.05)
            try:
                if all(self.query_one(f"#slash-{fl}", SlashDropdown) for fl in flavors):
                    break
            except Exception:  # noqa: BLE001
                continue
        try:
            commands = await self.client.list_commands()
        except Exception as exc:  # noqa: BLE001
            logger.warning("slash dropdown: list_commands failed: %s", exc)
            commands = []
        for fl in flavors:
            try:
                skills = await self.client.list_skills(fl)
            except Exception as exc:  # noqa: BLE001
                logger.warning("slash dropdown: list_skills(%s) failed: %s", fl, exc)
                skills = []
            try:
                tools_resp = await self.client.get_tools(fl)
                tools = (
                    tools_resp.get("tools", [])
                    if isinstance(tools_resp, dict)
                    else (tools_resp or [])
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("slash dropdown: get_tools(%s) failed: %s", fl, exc)
                tools = []
            try:
                self.query_one(f"#slash-{fl}", SlashDropdown).set_sources(
                    commands=commands, skills=skills, tools=tools
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("slash dropdown: set_sources(%s) failed: %s", fl, exc)
            # Pre-populate skills sidebar from API data (SSE events may not fire
            # for skills that were already installed before this session started).
            state = self._states.get(fl)
            pane = self._panes.get(fl)
            if state and pane and skills:
                state.preload_skills(skills)
                pane.sync_sidebar(state)

    def _focus_active_input(self) -> None:
        flavor = self._active_flavor()
        if not flavor:
            return
        try:
            self.query_one(f"#input-{flavor}", ChatInput).focus()
        except Exception:  # noqa: BLE001
            pass

    def _ensure_flavor(self, name: str) -> None:
        if name in self._states:
            return
        self._states[name] = FlavorState(name=name)
        tabs = self.query_one("#flavor-tabs", TabbedContent)
        pane = FlavorPane(flavor=name)
        self._panes[name] = pane
        tabs.add_pane(TabPane(name, pane, id=f"tab-{name}"))

    # ── SSE worker ───────────────────────────────────────────────────

    async def _sse_loop(self) -> None:
        try:
            async for kind, payload in stream_with_backoff(self.client):
                if kind == "event":
                    self._event_queue.put_nowait(payload)
                elif kind == "disconnect":
                    self.post_message(ConnectionStatusMessage("disconnected", payload))
                elif kind == "reconnecting":
                    self.post_message(ConnectionStatusMessage("reconnecting", payload))
                elif kind == "connected":
                    self.post_message(ConnectionStatusMessage("connected"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("SSE loop crashed: %s", exc)
            self.post_message(ConnectionStatusMessage("disconnected", exc))

    # ── Message dispatch ─────────────────────────────────────────────

    def on_connection_status_message(self, message: ConnectionStatusMessage) -> None:
        hdr = self.query_one(AppHeader)
        if message.kind == "connected":
            hdr.connected = True
            hdr.reconnecting = False
            hdr.auth_failed = False
            self._connected = True
            self.notify("Connected", severity="information", timeout=2)
        elif message.kind == "disconnected":
            hdr.connected = False
            hdr.reconnecting = False
            self._connected = False
            self.notify(f"Disconnected: {message.detail}", severity="warning")
        elif message.kind == "reconnecting":
            hdr.reconnecting = True
            self.notify(
                f"Reconnecting… (attempt {message.detail})", severity="information", timeout=2
            )

    async def _drain_events(self) -> None:
        """Drain SSE event queue once per 60fps frame — single layout pass per drain."""
        if self._event_queue.empty():
            return
        flavor = self._active_flavor()
        pane = self._panes.get(flavor)
        conv = pane.conversation if pane else None

        ctx = conv.suppress_scroll() if conv is not None else nullcontext()
        scrolled_active = False
        # No awaits inside the drain — atomicity required for get_nowait safety.
        with self.batch_update(), ctx:
            while not self._event_queue.empty():
                event = self._event_queue.get_nowait()
                self._debug_buffer.append(event)
                if self._debug_modal is not None:
                    self._debug_modal.push(event)
                event_flavor = event.flavor or self._active_flavor()
                self._dispatch_event(event)
                if event_flavor == flavor:
                    scrolled_active = True

        if conv is not None and scrolled_active:
            conv.scroll_end(animate=False)

    def _dispatch_event(self, event: SseEvent) -> None:
        flavor = event.flavor or self._active_flavor()
        if not flavor:
            return
        self._ensure_flavor(flavor)
        state = self._states[flavor]
        pane = self._panes.get(flavor)
        if pane is None:
            return

        if isinstance(event, PermissionRequiredEvent):
            self.run_worker(self._handle_permission(event), exclusive=False)
            return

        route_event(state, event)

        conv = pane.conversation
        if isinstance(event, AgentChunkEvent):
            conv.append_assistant(event.text)
        elif isinstance(event, AgentThinkingEvent):
            conv.append_thinking(event.text)
        elif isinstance(event, AgentTurnDoneEvent):
            conv.end_thinking()
            conv.end_assistant()
            self.run_worker(self._refresh_skills_for_flavor(flavor), exclusive=False)
        elif isinstance(event, ToolCallEvent):
            raw_cid = event.raw.get("call_id", "")
            if raw_cid:
                call_id = raw_cid
            elif _CALL_ID_RE.match(event.tool):
                # Completion event: backend sends tool=call_id with no call_id field.
                call_id = event.tool
            else:
                call_id = f"{event.tool}-{event.at}"
            tc = state.tool_calls[-1] if state.tool_calls else None
            # If the backend sent a raw call_id as the tool name, use the
            # human-readable title instead (both for the conv widget and the
            # state so the sidebar also shows the readable name).
            if _CALL_ID_RE.match(event.tool) and event.title:
                parts = event.title.split(": ", 1)
                tool_display = parts[0].strip()
                args_display = parts[1].strip() if len(parts) > 1 else event.title
                if tc is not None:
                    tc.tool = tool_display
                    tc.args = args_display
            else:
                tool_display = event.tool
                args_display = event.title or ""
            block = conv.get_tool(call_id)
            if block is None and not _CALL_ID_RE.match(event.tool):
                block = conv.start_tool(tool_display, args=args_display, call_id=call_id)
            if block is not None:
                if tc is not None:
                    block.set_status(tc.status)
                if event.output:
                    block.append_output(event.output)
        elif isinstance(event, SkillLoadedEvent):
            conv.start_skill(event.skill_name, event.skill_size)
        elif isinstance(event, FlavorStatusEvent):
            pass

        pane.set_state(state.state)
        pane.sync_sidebar(state)

        if flavor == self._active_flavor():
            self._refresh_status_bar(state)

    async def _handle_permission(self, event: PermissionRequiredEvent) -> None:
        if event.tool in self._always_allow_tools:
            await self.client.resolve_permission(event.permission_id, "allow")
            return
        decision = await self.push_screen_wait(
            PermissionModal(
                tool=event.tool,
                args=str(event.args),
                risk=event.risk,
                description=event.description,
            )
        )
        if decision == "always_allow":
            self._always_allow_tools.add(event.tool)
            await self.client.resolve_permission(event.permission_id, "allow")
        else:
            await self.client.resolve_permission(event.permission_id, decision or "deny")

    # ── Helpers ──────────────────────────────────────────────────────

    def _active_flavor(self) -> str:
        try:
            active = self.query_one("#flavor-tabs", TabbedContent).active
            if active and active.startswith("tab-"):
                return active[4:]
        except Exception:  # noqa: BLE001
            pass
        return next(iter(self._states), "")

    def _refresh_status_bar(self, state: FlavorState) -> None:
        bar = self.query_one(StatusBar)
        bar.flavor = state.name
        bar.state = state.state
        bar.tokens = state.token_usage.get("total", 0)

    # ── Input submission ─────────────────────────────────────────────

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        flavor = self._active_flavor()
        if not flavor:
            return
        state = self._states[flavor]
        state.clear_for_new_turn()
        self._panes[flavor].conversation.add_user_message(event.text)
        self._panes[flavor].set_state(AgentState.THINKING)
        self.run_worker(self._send_message(flavor, event.text), exclusive=False)

    async def _send_message(self, flavor: str, text: str) -> None:
        try:
            session_id = self._active_session_id.get(flavor)
            response = await self.client.send_message(flavor, text, session_id=session_id)
            self._current_correlation_id = response.get("correlation_id")
            # Remember the session id the server allocated so the next turn
            # continues to append to the same session (W7).
            new_sid = response.get("session_id")
            if new_sid:
                self._active_session_id[flavor] = new_sid
        except httpx.HTTPError as exc:
            self._states[flavor].set_error(str(exc))
            self._panes[flavor].set_state(AgentState.ERROR)
            self.notify(f"Send failed: {exc}", severity="error")

    # ── Slash autocomplete ───────────────────────────────────────────

    def on_chat_input_text_changed(self, event: ChatInput.TextChanged) -> None:
        flavor = self._active_flavor()
        if not flavor:
            return
        try:
            self.query_one(f"#slash-{flavor}", SlashDropdown).update_for_text(event.text)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.query_one(f"#files-{flavor}", FilePickerDropdown).update_for_text(event.text)
        except Exception:  # noqa: BLE001
            pass

    def on_slash_dropdown_completed(self, event: SlashDropdown.Completed) -> None:
        flavor = self._active_flavor()
        if not flavor:
            return
        try:
            inp = self.query_one(f"#input-{flavor}", ChatInput)
            # Replace whatever the user typed with the completed command + trailing space
            inp.text = event.command + " "
            inp.focus()
        except Exception:  # noqa: BLE001
            pass

    def on_file_picker_dropdown_completed(self, event: FilePickerDropdown.Completed) -> None:
        flavor = self._active_flavor()
        if not flavor:
            return
        try:
            inp = self.query_one(f"#input-{flavor}", ChatInput)
            # Replace the trailing @token with @path
            text = inp.text
            at = text.rfind("@")
            new_text = (text[:at] if at >= 0 else text) + f"@{event.path} "
            inp.text = new_text
            inp.focus()
        except Exception:  # noqa: BLE001
            pass

    # ── Search ───────────────────────────────────────────────────────

    def on_search_bar_query(self, event: SearchBar.Query) -> None:
        if not event.query:
            return
        self.notify(f"Search: {event.query}", timeout=1)

    def on_search_bar_dismiss(self, _event: SearchBar.Dismiss) -> None:
        flavor = self._active_flavor()
        if flavor and flavor in self._panes:
            self._panes[flavor].input.focus()

    # ── Actions (keybindings) ────────────────────────────────────────

    def action_command_palette(self) -> None:
        def on_dismissed(result: object) -> None:
            if isinstance(result, str) and result:
                self.run_worker(self._handle_command_action(result), exclusive=False)

        self.push_screen(CommandModal(default_commands()), on_dismissed)

    async def _handle_command_action(self, action: str) -> None:
        mapping: dict[str, str] = {
            "open_sessions": "open_sessions",
            "open_memory": "open_memory",
            "open_skills": "open_skills",
            "open_tools": "open_tools",
            "new_session": "new_session",
            "open_cost": "open_cost",
            "open_config": "open_config",
            "switch_flavor": "switch_flavor",
            "switch_model": "switch_model",
            "toggle_sidebar": "toggle_sidebar",
            "toggle_theme": "toggle_dark",
            "search": "search",
            "help": "help",
            "open_debug": "open_debug",
            "quit": "request_quit",
        }
        method = mapping.get(action)
        if method is None:
            return
        actor = getattr(self, f"action_{method}", None)
        if actor is None:
            return
        result = actor()
        if asyncio.iscoroutine(result):
            await result

    def action_open_sessions(self) -> None:
        self.run_worker(self._open_sessions(), exclusive=False)

    async def _open_sessions(self) -> None:
        try:
            raw = await self.client.list_sessions()
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Sessions unavailable: {exc}", severity="warning")
            raw = []
        sessions = [
            SessionEntry(
                session_id=s.get("id", ""),
                flavor=s.get("flavor", self._active_flavor()),
                title=s.get("title", "Untitled"),
                last_active=s.get("last_active", ""),
                message_count=int(s.get("message_count", 0)),
                preview=s.get("preview", ""),
            )
            for s in raw
        ]
        result = await self.push_screen_wait(SessionsModal(sessions))
        if isinstance(result, SessionAction):
            await self._handle_session_action(result)

    async def _handle_session_action(self, action: SessionAction) -> None:
        try:
            if action.action == "resume":
                await self._resume_session(action)
            elif action.action == "fork":
                await self.client.fork_session(action.session_id)
                self.notify(f"Forked {action.session_id[:8]}")
            elif action.action == "delete":
                confirmed = await self.push_screen_wait(
                    ConfirmModal("Delete this session? This cannot be undone.", dangerous=True)
                )
                if confirmed:
                    await self.client.delete_session(action.session_id)
                    self.notify("Session deleted")
            elif action.action == "new":
                self.notify("New session started")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Session action failed: {exc}", severity="error")

    async def _resume_session(self, action: SessionAction) -> None:
        """Server-side resume + replay history into ConversationView (W7).

        Cross-flavor: if the session lives in a different flavor than the
        active tab, switch tabs first (D7).
        """
        flavor = action.flavor or self._active_flavor()
        if not flavor:
            self.notify("No active flavor; can't resume", severity="warning")
            return

        # Switch tab if needed before we touch any of the flavor's UI.
        if self._active_flavor() != flavor:
            try:
                tabs = self.query_one("#flavor-tabs", TabbedContent)
                tabs.active = f"tab-{flavor}"
            except Exception:  # noqa: BLE001
                pass

        # Server-side resume (records "last active"), then pull messages.
        try:
            await self.client.resume_session(action.session_id)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Resume failed: {exc}", severity="warning")
            return

        try:
            rows = await self.client.get_session_messages(action.session_id, flavor=flavor)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Could not load history: {exc}", severity="warning")
            return

        pane = self._panes.get(flavor)
        if pane is None:
            self.notify(f"No pane for flavor {flavor!r}", severity="warning")
            return

        # Wipe local state + UI, then replay row-by-row.
        self._states[flavor] = FlavorState(name=flavor)
        pane.conversation.reset_for_replay()
        self._active_session_id[flavor] = action.session_id
        self._replay_messages(flavor, rows)
        self.notify(f"Resumed {action.session_id[:8]} — {len(rows)} msgs")

    def _replay_messages(
        self,
        flavor: str,
        rows: list[dict],
        unread_from_row: int | None = None,
    ) -> None:
        """Render historical DB rows as if they had just streamed live.

        Row shape (per podo/nx01#94): {role, content, tool_name, tool_calls,
        tool_call_id, reasoning, reasoning_content, timestamp, ...}.

        - reasoning text → ThinkingBlock, immediately finalised (collapsed)
        - role=user      → UserMessage
        - role=assistant → AssistantMessage; if tool_calls present, also
                            mount one ToolCallBlock per call (marked DONE)
        - role=tool      → tool output appended into the matching ToolCallBlock

        If unread_from_row is given, an UnreadDivider is inserted before that row.
        """
        from .state import ToolStatus

        conv = self._panes[flavor].conversation
        with self.batch_update(), conv.suppress_scroll():
            for i, row in enumerate(rows):
                if unread_from_row is not None and i == unread_from_row:
                    new_count = len(rows) - unread_from_row
                    conv.insert_unread_divider(new_count)

                role = row.get("role", "")
                reasoning = row.get("reasoning") or row.get("reasoning_content") or ""
                if reasoning:
                    t = conv.start_thinking()
                    t.append_chunk(reasoning)
                    conv.end_thinking(auto_collapse=True)

                if role == "user":
                    content = row.get("content") or ""
                    if content:
                        conv.add_user_message(str(content))
                elif role == "assistant":
                    content = row.get("content") or ""
                    if content:
                        conv.start_assistant(str(content))
                        conv.end_assistant()
                    for tc in row.get("tool_calls") or []:
                        name = tc.get("name") or tc.get("function", {}).get("name", "tool")
                        args = tc.get("arguments") or tc.get("function", {}).get("arguments", "")
                        call_id = tc.get("id", "")
                        block = conv.start_tool(tool=str(name), args=str(args), call_id=call_id)
                        block.set_status(ToolStatus.DONE)
                elif role == "tool":
                    call_id = row.get("tool_call_id", "")
                    tool_name = row.get("tool_name") or "tool"
                    output = row.get("content") or ""
                    block = conv.get_tool(call_id) if call_id else None
                    if block is None:
                        block = conv.start_tool(tool=str(tool_name), args="", call_id=call_id)
                    if output:
                        block.append_output(str(output))
                    block.set_status(ToolStatus.DONE)
        # Single scroll after all mounts — suppress_scroll is now released.
        conv.scroll_end(animate=False)

    def action_open_memory(self) -> None:
        self.run_worker(self._open_memory(), exclusive=False)

    async def _open_memory(self) -> None:
        flavor = self._active_flavor() or "assistant"
        try:
            agent = await self.client.read_memory("agent", flavor=flavor)
            user = await self.client.read_memory("user", flavor=flavor)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Memory unavailable: {exc}", severity="warning")
            agent, user = [], []
        await self.push_screen_wait(MemoryModal(agent_entries=agent, user_entries=user))

    def action_open_skills(self) -> None:
        self.run_worker(self._open_skills(), exclusive=False)

    async def _open_skills(self) -> None:
        try:
            skills = await self.client.list_skills(self._active_flavor())
        except Exception:  # noqa: BLE001
            skills = []
        await self.push_screen_wait(SkillsModal(skills))

    def action_open_tools(self) -> None:
        self.run_worker(self._open_tools(), exclusive=False)

    async def _open_tools(self) -> None:
        try:
            tools_resp = await self.client.get_tools(self._active_flavor())
            tools = tools_resp.get("tools", []) if isinstance(tools_resp, dict) else tools_resp
        except Exception:  # noqa: BLE001
            tools = []
        await self.push_screen_wait(ToolsModal(tools))

    def action_open_cost(self) -> None:
        flavor = self._active_flavor()
        cost = {"tokens": self._states[flavor].token_usage} if flavor in self._states else {}
        self.push_screen(CostModal(cost))

    def action_open_config(self) -> None:
        self.push_screen(
            ConfigModal({"base_url": self.base_url, "model": self.query_one(AppHeader).model})
        )

    def action_switch_model(self) -> None:
        self.run_worker(self._switch_model(), exclusive=False)

    async def _switch_model(self) -> None:
        try:
            models_resp = await self.client._client.get("/v1/models")
            data = models_resp.json()
            models = [m.get("id", "") for m in data.get("data", []) if isinstance(m, dict)]
        except Exception:  # noqa: BLE001
            models = []
        chosen = await self.push_screen_wait(ModelPickerModal(models))
        if chosen:
            self.query_one(AppHeader).model = chosen
            self.notify(f"Model: {chosen}")

    async def action_new_session(self) -> None:
        flavor = self._active_flavor()
        if flavor and flavor in self._states:
            self._states[flavor].clear_for_new_turn()
            self._states[flavor].messages = []
            self.notify(f"New session in {flavor}")

    def action_toggle_sidebar(self) -> None:
        for pane in self._panes.values():
            sidebar = pane.sidebar
            if sidebar.has_class("hidden"):
                sidebar.remove_class("hidden")
            else:
                sidebar.add_class("hidden")

    def action_search(self) -> None:
        flavor = self._active_flavor()
        if not flavor:
            return
        try:
            bar = self.query_one(f"#search-{flavor}", SearchBar)
            bar.show()
        except Exception:  # noqa: BLE001
            pass

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def action_open_debug(self) -> None:
        def on_dismissed(_result: object) -> None:
            self._debug_modal = None

        self._debug_modal = DebugModal(list(self._debug_buffer))
        self.push_screen(self._debug_modal, on_dismissed)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Yield ctrl+c / ctrl+y back to whichever modal owns focus.

        - When a `ModalScreen` is on top (Sessions filter Input, DebugModal
          with its own `ctrl+y → yank_buffer`, etc.), return False so the
          modal's own bindings + native Input/TextArea copy work normally.
        - In the main pane (no modal), the App actions fire as designed —
          ctrl+c stops generation, ctrl+y yanks the focused chunk, even
          when ChatInput owns focus. See QA-REVERIFY §R2/R3.
        """
        if action not in ("stop_generation", "yank_focused", "yank_last_code"):
            return True
        if self._modal_on_top():
            return False
        return True

    def _modal_on_top(self) -> bool:
        try:
            from textual.screen import ModalScreen

            return isinstance(self.screen, ModalScreen)
        except Exception:  # noqa: BLE001
            return False

    def action_request_quit(self) -> None:
        self._save_session_state()
        self.exit()

    def _save_session_state(self) -> None:
        sessions = {
            flavor: {"session_id": sid, "quit_ts": time.time()}
            for flavor, sid in self._active_session_id.items()
            if sid
        }
        try:
            _STATE_FILE.write_text(json.dumps({"version": 1, "sessions": sessions}))
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to save session state: %s", exc)

    async def _refresh_skills_for_flavor(self, flavor: str) -> None:
        try:
            skills = await self.client.list_skills(flavor)
        except Exception:  # noqa: BLE001
            return
        state = self._states.get(flavor)
        pane = self._panes.get(flavor)
        if state and pane and skills:
            state.preload_skills(skills)
            pane.sync_sidebar(state)

    async def _auto_resume_from_saved_state(self) -> None:
        if not _STATE_FILE.exists():
            return
        try:
            data = json.loads(_STATE_FILE.read_text())
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not load session state file: %s", exc)
            return
        if data.get("version") != 1:
            return
        for flavor, info in data.get("sessions", {}).items():
            session_id = info.get("session_id", "")
            quit_ts = float(info.get("quit_ts", 0))
            if not session_id or flavor not in self._states:
                continue
            try:
                await self._auto_resume_flavor(flavor, session_id, quit_ts)
            except Exception as exc:  # noqa: BLE001
                logger.warning("auto-resume %s failed: %s", flavor, exc)

    async def _auto_resume_flavor(self, flavor: str, session_id: str, quit_ts: float) -> None:
        try:
            await self.client.resume_session(session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto-resume server call failed for %s: %s", flavor, exc)
            return
        try:
            rows = await self.client.get_session_messages(session_id, flavor=flavor)
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto-resume get_messages failed for %s: %s", flavor, exc)
            return
        pane = self._panes.get(flavor)
        if pane is None:
            return

        # Find index of first row that arrived after the user quit.
        unread_from_row: int | None = None
        if quit_ts > 0:
            for i, row in enumerate(rows):
                ts = row.get("timestamp") or row.get("created_at") or 0
                if isinstance(ts, str):
                    try:
                        ts = (
                            datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            .replace(tzinfo=datetime.UTC)
                            .timestamp()
                        )
                    except Exception:  # noqa: BLE001
                        ts = 0
                if float(ts) > quit_ts:
                    unread_from_row = i
                    break

        self._states[flavor] = FlavorState(name=flavor)
        pane.conversation.reset_for_replay()
        self._active_session_id[flavor] = session_id
        self._replay_messages(flavor, rows, unread_from_row=unread_from_row)

        if unread_from_row is not None and unread_from_row < len(rows):
            new_count = len(rows) - unread_from_row
            pane.conversation.scroll_to_unread_after_refresh()
            self.notify(
                f"Resumed — {new_count} new message{'s' if new_count != 1 else ''}",
                timeout=4,
            )
        else:
            pane.conversation.scroll_end(animate=False)

    def action_stop_generation(self) -> None:
        if self._current_correlation_id:
            self.run_worker(self.client.abort(self._current_correlation_id), exclusive=False)
            self.notify("Stop sent")

    def action_switch_flavor(self) -> None:
        tabs = self.query_one("#flavor-tabs", TabbedContent)
        names = list(self._states)
        if not names:
            return
        current = self._active_flavor()
        idx = (names.index(current) + 1) % len(names) if current in names else 0
        tabs.active = f"tab-{names[idx]}"

    def action_select_flavor(self, index: int) -> None:
        """Jump directly to flavor[index]; no-op past the end (D9, #26)."""
        names = list(self._states)
        if not names or index < 0 or index >= len(names):
            return
        tabs = self.query_one("#flavor-tabs", TabbedContent)
        tabs.active = f"tab-{names[index]}"

    def action_yank_focused(self) -> None:
        flavor = self._active_flavor()
        if not flavor:
            return
        state = self._states[flavor]
        for msg in reversed(state.messages):
            if msg.get("type") == "chunk" and msg.get("text"):
                self._copy(msg["text"])
                return
        self.notify("Nothing to copy")

    def action_yank_last_code(self) -> None:
        flavor = self._active_flavor()
        if not flavor:
            return
        for msg in reversed(self._states[flavor].messages):
            if msg.get("type") == "chunk":
                code = self._extract_last_code_block(msg.get("text", ""))
                if code:
                    self._copy(code)
                    return
        self.notify("No code block")

    @staticmethod
    def _extract_last_code_block(text: str) -> str:
        lines = text.splitlines()
        end = -1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].startswith("```"):
                end = i
                break
        if end <= 0:
            return ""
        start = -1
        for i in range(end - 1, -1, -1):
            if lines[i].startswith("```"):
                start = i
                break
        if start < 0:
            return ""
        return "\n".join(lines[start + 1 : end])

    def _copy(self, text: str) -> None:
        try:
            self.copy_to_clipboard(text)
            self.notify(f"Copied {len(text)} chars")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Copy failed: {exc}", severity="error")

    # ── Tab change ───────────────────────────────────────────────────

    def on_tabbed_content_tab_activated(self, _event: TabbedContent.TabActivated) -> None:
        flavor = self._active_flavor()
        if flavor and flavor in self._states:
            self._refresh_status_bar(self._states[flavor])
            self._focus_active_input()

    # ── Responsive ───────────────────────────────────────────────────

    def on_resize(self, event) -> None:  # type: ignore[no-untyped-def]
        width = event.size.width
        for pane in self._panes.values():
            # Sidebar may not be mounted yet on the very first resize event
            # (fires before FlavorPane.compose finishes) — skip gracefully.
            try:
                pane.sidebar.apply_terminal_width(width)
            except Exception:  # noqa: BLE001
                continue


# Back-compat alias for CLI: existing entry point used `Nx01TuiApp`.
Nx01TuiApp = Nx01App
