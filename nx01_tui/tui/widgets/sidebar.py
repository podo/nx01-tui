"""MonitorSidebar — right-docked dashboard with 5 sections.

Sections (per DESIGN.md §5):
    Activity   – live tool call rows (per-flavor)
    Memory     – agent + user store progress bars (global)
    Skills     – session-loaded skills (per-flavor)
    Context    – token usage bar (per-flavor)
    Session    – metadata (per-flavor)
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import ProgressBar, Static

from ..state import FlavorState, ToolStatus

# ── Section primitive ──────────────────────────────────────────────────


class _Section(Vertical):
    DEFAULT_CSS = """
    _Section {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
    }
    _Section .section-title {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 0;
    }
    """

    def __init__(self, title: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._title = title

    def compose(self) -> ComposeResult:
        yield Static(self._title.upper(), classes="section-title")


# ── Activity ───────────────────────────────────────────────────────────


class ActivitySection(_Section):
    DEFAULT_CSS = """
    ActivitySection { height: auto; min-height: 4; }
    ActivitySection #activity-rows { height: auto; max-height: 12; }
    ActivitySection #activity-summary { color: $text-muted; height: 1; }
    """

    def __init__(self) -> None:
        super().__init__(title="Activity")

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield VerticalScroll(id="activity-rows")
        yield Static("[dim]no activity[/]", id="activity-summary")

    def update_from(self, state: FlavorState) -> None:
        try:
            rows = self.query_one("#activity-rows", VerticalScroll)
        except Exception:  # noqa: BLE001
            return
        rows.remove_children()
        for tc in state.tool_calls[-10:]:
            icon = {
                ToolStatus.QUEUED: "[dim]○[/]",
                ToolStatus.ACTIVE: "[$success]✻[/]",
                ToolStatus.DONE: "[$success]✓[/]",
                ToolStatus.ERROR: "[$error]✗[/]",
            }[tc.status]
            label = f"{icon} [bold]{tc.tool}[/] [dim]{tc.args[:18]}[/] [dim]{tc.elapsed_str()}[/]"
            rows.mount(Static(label))
        done, active, queued = state.activity_summary()
        try:
            self.query_one("#activity-summary", Static).update(
                f"[dim]{done} done · {active} active · {queued} queued[/]"
            )
        except Exception:  # noqa: BLE001
            pass


# ── Memory ─────────────────────────────────────────────────────────────


class MemorySection(_Section):
    DEFAULT_CSS = """
    MemorySection ProgressBar { width: 1fr; height: 1; margin: 0 0 0 0; }
    MemorySection Bar > .bar--bar { color: $success; }
    MemorySection .row { height: 1; }
    MemorySection .label-row { color: $text-muted; }
    MemorySection #mem0-row { color: $text-muted; height: 1; }
    """

    AGENT_LIMIT = 2200
    USER_LIMIT = 1375

    agent_chars: reactive[int] = reactive(0)
    user_chars: reactive[int] = reactive(0)

    def __init__(self) -> None:
        super().__init__(title="Memory")

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Static(
            self._label("agent", 0, self.AGENT_LIMIT), classes="label-row", id="agent-label"
        )
        yield ProgressBar(
            total=self.AGENT_LIMIT, show_eta=False, show_percentage=False, id="agent-bar"
        )
        yield Static(self._label("user", 0, self.USER_LIMIT), classes="label-row", id="user-label")
        yield ProgressBar(
            total=self.USER_LIMIT, show_eta=False, show_percentage=False, id="user-bar"
        )
        yield Static("[dim]mem0[/]  off", id="mem0-row")

    def _label(self, name: str, used: int, limit: int) -> str:
        pct = (used / limit) * 100 if limit else 0
        color = "$success" if pct < 75 else ("$warning" if pct < 90 else "$error")
        if used > limit:
            over = used - limit
            return (
                f"[{color}]{name}[/]  [dim]{used:,} / {limit:,}[/]"
                f"  [$error]+{over:,} over · /compact[/]"
            )
        return f"[{color}]{name}[/]  [dim]{used:,} / {limit:,}[/]"

    def watch_agent_chars(self, value: int) -> None:
        try:
            self.query_one("#agent-bar", ProgressBar).progress = value
            self.query_one("#agent-label", Static).update(
                self._label("agent", value, self.AGENT_LIMIT)
            )
        except Exception:  # noqa: BLE001
            pass

    def watch_user_chars(self, value: int) -> None:
        try:
            self.query_one("#user-bar", ProgressBar).progress = value
            self.query_one("#user-label", Static).update(
                self._label("user", value, self.USER_LIMIT)
            )
        except Exception:  # noqa: BLE001
            pass

    def set_mem0_status(self, status: str) -> None:
        """Update the mem0 row. Call with 'active' when ADR 0012 ships."""
        try:
            color = "$success" if status == "active" else "$text-muted"
            self.query_one("#mem0-row", Static).update(f"[{color}]mem0[/]  {status}")
        except Exception:  # noqa: BLE001
            pass


# ── Skills ─────────────────────────────────────────────────────────────


class SkillsSection(_Section):
    DEFAULT_CSS = """
    SkillsSection #skills-list { height: auto; max-height: 6; }
    """

    def __init__(self) -> None:
        super().__init__(title="Skills")

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Vertical(id="skills-list")

    def update_from(self, state: FlavorState) -> None:
        try:
            container = self.query_one("#skills-list", Vertical)
        except Exception:  # noqa: BLE001
            return
        container.remove_children()
        if not state.skills_loaded:
            container.mount(Static("[dim]no skills loaded[/]"))
            return
        for skill in state.skills_loaded[-6:]:
            kb = skill.get("size", 0) / 1024
            size_str = f"  [dim]{kb:.1f}kb[/]" if skill.get("size") else ""
            container.mount(Static(f"[$accent]◆[/] [bold]{skill['name']}[/]{size_str}"))


# ── MCP server status (V2 — populated from /mcp/servers endpoint) ────


class McpSection(_Section):
    DEFAULT_CSS = """
    McpSection .mcp-row { color: $text-muted; height: 1; }
    """

    def __init__(self) -> None:
        super().__init__(title="MCP")

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Vertical(id="mcp-list")

    def update_servers(self, servers: list[dict]) -> None:
        try:
            container = self.query_one("#mcp-list", Vertical)
        except Exception:  # noqa: BLE001
            return
        container.remove_children()
        if not servers:
            container.mount(Static("[dim]none[/]", classes="mcp-row"))
            return
        for srv in servers[-6:]:
            status = (srv.get("status") or "unknown").lower()
            color = {
                "connected": "$success",
                "running": "$success",
                "needs_auth": "$warning",
                "error": "$error",
                "failed": "$error",
            }.get(status, "$text-muted")
            container.mount(
                Static(
                    f"[{color}]⬤[/] [bold]{srv.get('name', '?')}[/]  [dim]{status}[/]",
                    classes="mcp-row",
                )
            )


# ── Context ────────────────────────────────────────────────────────────


class ContextSection(_Section):
    DEFAULT_CSS = """
    ContextSection ProgressBar { width: 1fr; height: 1; }
    ContextSection .ctx-row { color: $text-muted; height: 1; }
    ContextSection #context-label { color: $text-muted; }
    """

    DEFAULT_LIMIT = 200_000

    tokens: reactive[int] = reactive(0)
    input_tokens: reactive[int] = reactive(0)
    output_tokens: reactive[int] = reactive(0)
    limit: reactive[int] = reactive(DEFAULT_LIMIT)

    def __init__(self) -> None:
        super().__init__(title="Context")

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Static(self._context_label(0, self.DEFAULT_LIMIT), id="context-label")
        yield ProgressBar(
            total=self.DEFAULT_LIMIT, show_eta=False, show_percentage=False, id="context-bar"
        )
        yield Static("[dim]in [/]  0", classes="ctx-row", id="input-label")
        yield Static("[dim]out[/]  0", classes="ctx-row", id="output-label")
        yield Static("[dim]cost[/] —", classes="ctx-row", id="cost-label")

    def _context_label(self, used: int, limit: int) -> str:
        pct = (used / limit) * 100 if limit else 0
        color = "$success" if pct < 60 else ("$warning" if pct < 80 else "$error")
        return f"[dim]{used:,} / {limit:,}[/]  [{color}]{pct:.0f}%[/]"

    def _refresh(self) -> None:
        try:
            self.query_one("#context-bar", ProgressBar).progress = self.tokens
            self.query_one("#context-label", Static).update(
                self._context_label(self.tokens, self.limit)
            )
            self.query_one("#input-label", Static).update(f"[dim]in [/]  {self.input_tokens:,}")
            self.query_one("#output-label", Static).update(f"[dim]out[/]  {self.output_tokens:,}")
        except Exception:  # noqa: BLE001
            pass

    def watch_tokens(self, _: int) -> None:
        self._refresh()

    def watch_input_tokens(self, _: int) -> None:
        self._refresh()

    def watch_output_tokens(self, _: int) -> None:
        self._refresh()


# ── Session ────────────────────────────────────────────────────────────


class SessionSection(_Section):
    DEFAULT_CSS = """
    SessionSection .session-row { color: $text-muted; height: 1; }
    """

    def __init__(self) -> None:
        super().__init__(title="Session")

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Static("[dim]title[/]  —", classes="session-row", id="session-title-row")
        yield Static("[dim]msgs[/]   0", classes="session-row", id="session-msgs-row")
        yield Static("[dim]flavor[/] —", classes="session-row", id="session-flavor-row")

    def update_from(self, state: FlavorState) -> None:
        try:
            self.query_one("#session-title-row", Static).update(
                f"[dim]title[/]  {state.session_title or '—'}"
            )
            self.query_one("#session-msgs-row", Static).update(
                f"[dim]msgs[/]   {len(state.messages)}"
            )
            self.query_one("#session-flavor-row", Static).update(f"[dim]flavor[/] {state.name}")
        except Exception:  # noqa: BLE001
            pass


# ── Session Health ─────────────────────────────────────────────────────


class SessionHealthSection(_Section):
    """Top-of-sidebar health card: agent state, message count, session ID."""

    DEFAULT_CSS = """
    SessionHealthSection { border-bottom: solid $panel; padding-bottom: 1; }
    SessionHealthSection .health-row { height: 1; }
    """

    _STATE_ICONS: dict[str, str] = {
        "idle": "○",
        "thinking": "◌",
        "streaming": "◎",
        "tool_call": "◉",
        "done": "●",
        "error": "✗",
    }

    _STATE_COLORS: dict[str, str] = {
        "idle": "$text-muted",
        "thinking": "$warning",
        "streaming": "$accent",
        "tool_call": "$success",
        "done": "$success",
        "error": "$error",
    }

    def __init__(self) -> None:
        super().__init__(title="Health")

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Static("○ idle", classes="health-row", id="health-state")
        yield Static("[dim]msgs[/]  0", classes="health-row", id="health-msgs")
        yield Static("[dim]sess[/]  —", classes="health-row", id="health-sess")

    def update_from(self, state: FlavorState) -> None:
        state_name = state.state.value if hasattr(state.state, "value") else str(state.state)
        icon = self._STATE_ICONS.get(state_name, "?")
        color = self._STATE_COLORS.get(state_name, "$text-muted")
        sess = state.session_id
        sess_short = (sess[:8] + "…") if len(sess) > 8 else (sess or "—")
        try:
            self.query_one("#health-state", Static).update(f"[{color}]{icon} {state_name}[/]")
            self.query_one("#health-msgs", Static).update(f"[dim]msgs[/]  {len(state.messages)}")
            self.query_one("#health-sess", Static).update(f"[dim]sess[/]  {sess_short}")
        except Exception:  # noqa: BLE001
            pass


# ── Sidebar container ──────────────────────────────────────────────────


class MonitorSidebar(Vertical):
    """Right-docked monitoring panel; per-flavor instance."""

    DEFAULT_CSS = """
    MonitorSidebar {
        width: 30;
        height: 1fr;
        border-left: solid $panel;
        background: $surface;
        padding: 0 0 0 0;
    }
    MonitorSidebar.hidden { display: none; }
    """

    def __init__(self, flavor: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.flavor = flavor

    def compose(self) -> ComposeResult:
        yield SessionHealthSection()
        yield ActivitySection()
        yield MemorySection()
        yield SkillsSection()
        yield McpSection()
        yield ContextSection()
        yield SessionSection()

    # ── Reactive update entry point ──────────────────────────────────

    def update_from(self, state: FlavorState) -> None:
        """Sync the entire sidebar from a FlavorState snapshot."""
        try:
            self.query_one(SessionHealthSection).update_from(state)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.query_one(ActivitySection).update_from(state)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.query_one(SkillsSection).update_from(state)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.query_one(McpSection).update_servers(state.mcp_servers)
        except Exception:  # noqa: BLE001
            pass
        try:
            ctx = self.query_one(ContextSection)
            ctx.tokens = state.token_usage.get("total", 0)
            ctx.input_tokens = state.token_usage.get("input", 0)
            ctx.output_tokens = state.token_usage.get("output", 0)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.query_one(SessionSection).update_from(state)
        except Exception:  # noqa: BLE001
            pass

    def set_memory(self, agent_chars: int, user_chars: int) -> None:
        try:
            mem = self.query_one(MemorySection)
            mem.agent_chars = agent_chars
            mem.user_chars = user_chars
        except Exception:  # noqa: BLE001
            pass

    # ── Responsive behaviour ─────────────────────────────────────────

    # Hard limits for the responsive width (cells). Override per-instance if
    # a different sidebar should bias narrower or wider.
    MIN_WIDTH = 30
    MAX_WIDTH = 50

    def apply_terminal_width(self, width: int) -> None:
        self.remove_class("hidden")
        # Hide entirely below 130 cols (#29 item 3). The previous icon-strip
        # mode rendered an empty 3-col sliver because no per-section icons
        # exist; the StatusBar surfaces a `ctrl+b` hint instead.
        if width < 130:
            self.add_class("hidden")
            return
        # Normal mode — scale linearly with terminal width, clamped to
        # [MIN_WIDTH, MAX_WIDTH].
        target = max(self.MIN_WIDTH, min(self.MAX_WIDTH, width // 4))
        self.styles.width = target
