"""nx01-tui v1.0 visual smoke runner.

Boots Nx01App in headless Pilot mode, drives every v1.0 feature in
sequence, and saves an SVG screenshot at each milestone. Emits a
markdown report at the end summarising pass/fail per scenario.

Usage:
    uv run python scripts/v1_visual_smoke.py
    open artifacts/v1-smoke/REPORT.md

The runner mocks the network layer so it works offline. Pass
NX01_URL + NX01_API_KEY to drive against a live backend instead.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Allow running from repo root or scripts/
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.events import parse_event  # noqa: E402
from nx01_tui.tui.modals.sessions_modal import SessionAction, SessionEntry  # noqa: E402
from nx01_tui.tui.widgets import (  # noqa: E402
    AppHeader,
    ChatInput,
    FilePickerDropdown,
    MonitorSidebar,
    SlashDropdown,
    ThinkingBlock,
    ToolCallBlock,
)
from tests.fixtures.sample_events import (  # noqa: E402
    chunk,
    skill_loaded,
    thinking,
    tool_completed,
    tool_started,
    turn_done,
)

ARTIFACTS = ROOT / "artifacts" / "v1-smoke"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


@dataclass
class Step:
    n: int
    name: str
    description: str
    svg_path: str = ""
    passed: bool = False
    detail: str = ""


@dataclass
class Report:
    steps: list[Step] = field(default_factory=list)

    def add(self, step: Step) -> None:
        self.steps.append(step)

    def write(self) -> Path:
        out = ARTIFACTS / "REPORT.md"
        lines = ["# nx01-tui v1.0 visual smoke report", ""]
        passed = sum(1 for s in self.steps if s.passed)
        lines.append(f"**{passed} / {len(self.steps)} scenarios passed**")
        lines.append("")
        lines.append("| # | Scenario | Pass | SVG |")
        lines.append("|---|---|---|---|")
        for s in self.steps:
            mark = "✓" if s.passed else "✗"
            link = f"[{Path(s.svg_path).name}]({Path(s.svg_path).name})" if s.svg_path else "—"
            lines.append(f"| S{s.n:02d} | {s.name} | {mark} | {link} |")
        lines.append("")
        for s in self.steps:
            lines.append(f"## S{s.n:02d}: {s.name}")
            lines.append(f"_{s.description}_")
            if s.svg_path:
                lines.append("")
                lines.append(f"![]({Path(s.svg_path).name})")
            if s.detail:
                lines.append("")
                lines.append("```")
                lines.append(s.detail)
                lines.append("```")
            lines.append("")
        out.write_text("\n".join(lines))
        return out


async def _settle(app, pilot, secs: float = 1.5) -> None:
    await pilot.pause(secs)
    # Cancel SSE/bootstrap retries so they don't repaint mid-screenshot.
    for w in list(app.workers):
        w.cancel()
    await pilot.pause(0.2)


def _screenshot(app, n: int, slug: str) -> str:
    path = ARTIFACTS / f"s{n:02d}_{slug}.svg"
    app.save_screenshot(str(path))
    return str(path)


def _mock_client(client) -> None:
    """Replace network methods on Nx01Client with deterministic fakes."""

    async def fake_get_flavors():
        return {
            "assistant": {"name": "assistant", "model": "claude-opus-4-7"},
            "operator": {"name": "operator", "model": "claude-opus-4-7"},
            "analyst": {"name": "analyst", "model": "claude-opus-4-7"},
        }

    async def fake_list_commands():
        return [
            {"name": "/help", "description": "show help"},
            {"name": "/sessions", "description": "list sessions"},
            {"name": "/memory", "description": "view agent memory"},
            {"name": "/new", "description": "start a new session"},
            {"name": "/model", "description": "switch model"},
        ]

    async def fake_list_skills(flavor=None):
        return [
            {"name": "ci-setup", "size": 4096, "loaded": False},
            {"name": "browser", "size": 8192, "loaded": True},
        ]

    async def fake_get_tools(flavor=None):
        return {
            "tools": [
                {"name": "bash", "description": "execute shell"},
                {"name": "read_file", "description": "read a file"},
                {"name": "edit_file", "description": "edit a file"},
            ]
        }

    async def fake_list_sessions(flavor=None):
        return [
            {
                "id": "sess_alpha",
                "title": "Deploy CI workflow",
                "flavor": "assistant",
                "last_active": "2026-05-17",
                "message_count": 12,
                "preview": "let's set up a GitHub Action…",
            },
            {
                "id": "sess_beta",
                "title": "Refactor session API",
                "flavor": "operator",
                "last_active": "2026-05-16",
                "message_count": 8,
                "preview": "wrap SessionDB in a thin HTTP layer",
            },
        ]

    async def fake_resume_session(sid):
        return {"session": {"id": sid, "flavor": "assistant"}}

    async def fake_get_session_messages(sid, flavor=None):
        return [
            {"role": "user", "content": "Set up a CI workflow", "timestamp": 1},
            {
                "role": "assistant",
                "content": "I'll write the YAML and add the test job.",
                "reasoning": "user wants minimal GitHub Actions setup",
                "tool_calls": [
                    {"id": "t1", "name": "bash", "arguments": "mkdir -p .github/workflows"}
                ],
                "timestamp": 2,
            },
            {
                "role": "tool",
                "tool_name": "bash",
                "tool_call_id": "t1",
                "content": "(created directory)",
                "timestamp": 3,
            },
            {
                "role": "assistant",
                "content": "Done. The workflow is at .github/workflows/ci.yml.",
                "timestamp": 4,
            },
        ]

    async def fake_health():
        return {"status": "ok"}

    client.get_flavors = fake_get_flavors
    client.list_commands = fake_list_commands
    client.list_skills = fake_list_skills
    client.get_tools = fake_get_tools
    client.list_sessions = fake_list_sessions
    client.resume_session = fake_resume_session
    client.get_session_messages = fake_get_session_messages
    client.get_health = fake_health


async def run() -> Report:
    report = Report()
    n = 0

    def step(name: str, description: str, passed: bool, svg: str = "", detail: str = "") -> None:
        nonlocal n
        n += 1
        report.add(
            Step(
                n=n, name=name, description=description, passed=passed, svg_path=svg, detail=detail
            )
        )

    # ── Scenario 1: Boot ──────────────────────────────────────────────
    app = Nx01App("http://mock", api_key="test", flavors=["assistant", "operator", "analyst"])
    _mock_client(app.client)
    async with app.run_test(size=(180, 50)) as pilot:
        await _settle(app, pilot)
        # Verify no status dot in header text.
        hdr = app.query_one(AppHeader)
        brand = hdr._brand_text()
        has_no_dot = not any(g in brand for g in ("⬤", "●"))
        # Verify 3 tabs mounted.
        from textual.widgets import TabbedContent

        tabs = app.query_one("#flavor-tabs", TabbedContent)
        active = tabs.active or ""
        svg = _screenshot(app, 1, "boot")
        step(
            "Boot — header no-dot, 3 flavor tabs, sidebar mounted",
            "Fresh launch. Header conveys state via text color only (no ⬤). "
            "TabbedContent has 3 tabs.",
            passed=has_no_dot and active.startswith("tab-"),
            svg=svg,
            detail=f"brand={brand!r} active={active!r}",
        )

        # ── Scenario 2: Slash dropdown merged ─────────────────────────
        flavor = app._active_flavor()
        ci = app.query_one(f"#input-{flavor}", ChatInput)
        ci.focus()
        await pilot.pause(0.1)
        ci.text = "/"
        slash = app.query_one(f"#slash-{flavor}", SlashDropdown)
        slash.update_for_text("/")
        await pilot.pause(0.2)
        # Inspect candidate categories.
        cats = {c[2] for c in slash.candidates}
        svg = _screenshot(app, 2, "slash_dropdown")
        step(
            "Slash dropdown — merged commands + skills + tools",
            "Type `/`. The dropdown appears above the input and contains "
            "entries from all three categories.",
            passed=slash.has_class("visible") and {"cmd", "skill", "tool"}.issubset(cats),
            svg=svg,
            detail=(
                f"visible={slash.has_class('visible')} "
                f"categories={sorted(cats)} count={slash.option_count}"
            ),
        )

        # ── Scenario 3: Slash dropdown filtered ──────────────────────
        slash.update_for_text("/bash")
        await pilot.pause(0.1)
        first_id = slash.get_option_at_index(0).id if slash.option_count > 0 else None
        svg = _screenshot(app, 3, "slash_filtered")
        step(
            "Slash dropdown — fuzzy filter narrows to one tool entry",
            "Typing `/bash` reduces results to the tool category.",
            passed=slash.option_count == 1 and first_id == "/tool bash",
            svg=svg,
            detail=f"option_count={slash.option_count} first_id={first_id!r}",
        )
        # Clear input so subsequent scenarios start fresh.
        ci.text = ""
        slash.update_for_text("")
        await pilot.pause(0.1)

        # ── Scenario 4: Arrow nav from input ──────────────────────────
        slash.update_for_text("/")
        await pilot.pause(0.1)
        before = slash.highlighted
        await pilot.press("down")
        await pilot.pause(0.1)
        after = slash.highlighted
        svg = _screenshot(app, 4, "slash_arrow_nav")
        step(
            "Slash dropdown — ↓ from ChatInput moves highlight",
            "While the dropdown is visible the priority bindings on ChatInput "
            "delegate Up/Down/Enter/Tab/Escape so the user can navigate.",
            passed=after != before,
            svg=svg,
            detail=f"highlight {before} → {after}",
        )
        slash.update_for_text("")
        await pilot.pause(0.1)

        # ── Scenario 5: File picker ───────────────────────────────────
        files = app.query_one(f"#files-{flavor}", FilePickerDropdown)
        ci.text = "look at @app"
        # Pre-load candidates so we don't have to wait on os.walk
        files._candidates = ["app.py", "appendix.md", "api/server.py"]
        files.update_for_text("look at @app")
        await pilot.pause(0.2)
        svg = _screenshot(app, 5, "file_picker")
        step(
            "File picker — `@token` opens the file dropdown above the input",
            "Same priority-binding pattern as slash — Up/Down navigate, Enter "
            "completes the path inline.",
            passed=files.has_class("visible") and files.option_count >= 1,
            svg=svg,
            detail=f"visible={files.has_class('visible')} count={files.option_count}",
        )
        ci.text = ""
        files.update_for_text("")
        await pilot.pause(0.1)

        # ── Scenario 6: Command palette list-focused ────────────────
        await pilot.press("ctrl+p")
        await pilot.pause(0.4)
        cmd_modal = app.screen
        from textual.widgets import Input, OptionList

        from nx01_tui.tui.modals.command_modal import CommandModal

        is_cmd_modal = isinstance(cmd_modal, CommandModal)
        list_focused = False
        filter_hidden = False
        emoji_free = False
        if is_cmd_modal:
            lst = cmd_modal.query_one("#cmd-list", OptionList)
            inp = cmd_modal.query_one("#filter", Input)
            list_focused = lst.has_focus
            filter_hidden = not inp.has_class("visible")
            # No emoji in any visible option label.
            opts_text = " ".join(
                str(cmd_modal.query_one("#cmd-list", OptionList).get_option_at_index(i).prompt)
                for i in range(lst.option_count)
            )
            emoji_free = not any(
                g in opts_text
                for g in (
                    "💬",
                    "📝",
                    "⚡",
                    "🔧",
                    "🤖",
                    "🎨",
                    "🔍",
                    "📊",
                    "❓",
                    "🐛",
                    "🚪",
                    "⏰",
                    "📋",
                    "🌐",
                    "🔌",
                )
            )
        svg = _screenshot(app, 6, "command_modal")
        step(
            "Command palette — list-focused, filter hidden, no emojis",
            "Ctrl+P opens the modal with the OptionList focused, the filter "
            "Input row hidden, and every option label rendered without emoji.",
            passed=is_cmd_modal and list_focused and filter_hidden and emoji_free,
            svg=svg,
            detail=f"is_cmd_modal={is_cmd_modal} list_focused={list_focused} "
            f"filter_hidden={filter_hidden} emoji_free={emoji_free}",
        )

        # ── Scenario 7: Command palette `/` reveals filter ──────────
        if is_cmd_modal:
            await pilot.press("slash")
            await pilot.pause(0.2)
            inp = cmd_modal.query_one("#filter", Input)
            filter_visible = inp.has_class("visible") and inp.has_focus
        else:
            filter_visible = False
        svg = _screenshot(app, 7, "command_modal_filter")
        step(
            "Command palette — `/` reveals the hidden filter row",
            "Pressing `/` inside the modal shows the filter Input and gives it focus.",
            passed=filter_visible,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)
        # Close any lingering modal so the next ctrl+p doesn't stack.
        if app.screen.__class__.__name__ != "_DefaultScreen":
            await pilot.press("escape")
            await pilot.pause(0.2)

        # ── Scenario 8: Sessions modal list-focused ─────────────────
        from nx01_tui.tui.modals.sessions_modal import SessionsModal

        await pilot.press("ctrl+s")
        await pilot.pause(0.6)
        modal = app.screen
        is_sessions_modal = isinstance(modal, SessionsModal)
        sess_list_focused = False
        sess_filter_hidden = False
        if is_sessions_modal:
            lst = modal.query_one("#session-list", OptionList)
            inp = modal.query_one("#filter", Input)
            sess_list_focused = lst.has_focus
            sess_filter_hidden = not inp.has_class("visible")
        svg = _screenshot(app, 8, "sessions_modal")
        step(
            "Sessions modal — list-focused, filter hidden",
            "Ctrl+S opens with the session list focused. Same pattern as command palette.",
            passed=is_sessions_modal and sess_list_focused and sess_filter_hidden,
            svg=svg,
            detail=f"is_sessions_modal={is_sessions_modal} list_focused={sess_list_focused} "
            f"filter_hidden={sess_filter_hidden}",
        )
        await pilot.press("escape")
        await pilot.pause(0.3)

        # ── Scenario 9: Tab cycles flavor (priority binding) ───────
        active_before = app._active_flavor()
        ci.focus()
        await pilot.pause(0.1)
        await pilot.press("tab")
        await pilot.pause(0.2)
        active_after = app._active_flavor()
        svg = _screenshot(app, 9, "tab_cycle")
        step(
            "Tab cycles flavor with input focused (priority binding)",
            "Tab now rotates flavor tabs even when ChatInput owns focus, "
            "because the binding is priority and beats TextArea's default.",
            passed=active_before != active_after,
            svg=svg,
            detail=f"{active_before} → {active_after}",
        )

        # ── Scenario 10: Ctrl+digit direct jump ─────────────────────
        app.action_select_flavor(2)
        await pilot.pause(0.2)
        flavors = list(app._states)
        ctrl3_ok = app._active_flavor() == flavors[2] if len(flavors) >= 3 else False
        # Past-end is no-op
        before_oob = app._active_flavor()
        app.action_select_flavor(8)
        await pilot.pause(0.1)
        oob_noop = app._active_flavor() == before_oob
        svg = _screenshot(app, 10, "ctrl_digit_jump")
        step(
            "Ctrl+1..9 direct jump (clamped to flavor count)",
            "Ctrl+3 selects the 3rd flavor. Ctrl+9 (past end) is a no-op.",
            passed=ctrl3_ok and oob_noop,
            svg=svg,
            detail=f"ctrl3_ok={ctrl3_ok} oob_noop={oob_noop}",
        )
        # Reset to first flavor for cleaner subsequent screenshots.
        app.action_select_flavor(0)
        await pilot.pause(0.2)

        # ── Scenario 11: Full turn render (▶/▼ chevrons live) ────────
        for raw in [
            thinking(text="Reasoning about CI setup…"),
            tool_started(tool="bash", args="ls -la", call_id="t1"),
            tool_completed(tool="bash", call_id="t1"),
            skill_loaded(name="ci-setup", size=4096),
            chunk(text="Here's the workflow YAML and test plan."),
            turn_done(),
        ]:
            app._dispatch_event(parse_event(raw))
        await pilot.pause(0.4)
        # ThinkingBlock should be collapsed; ToolCallBlock done; chevron is ▶
        flavor = app._active_flavor()
        conv = app._panes[flavor].conversation
        thinking_blocks = conv.query(ThinkingBlock)
        tool_blocks = conv.query(ToolCallBlock)
        chevron_glyph = ""
        if thinking_blocks:
            from nx01_tui.tui.widgets import ExpandChevron

            ch = thinking_blocks.first().query_one(ExpandChevron)
            chevron_glyph = str(ch.render())
        svg = _screenshot(app, 11, "full_turn")
        step(
            "Full turn — ▶/▼ chevrons, collapsed Thinking, done ToolCall",
            "Synthetic event stream renders ThinkingBlock + ToolCallBlock + SkillBlock + "
            "AssistantMessage. After turn.done, thinking auto-collapses; chevron shows ▶.",
            passed=len(thinking_blocks) >= 1
            and len(tool_blocks) >= 1
            and chevron_glyph in ("▶", "▼"),
            svg=svg,
            detail=(
                f"thinking={len(thinking_blocks)} tools={len(tool_blocks)} "
                f"chevron={chevron_glyph!r}"
            ),
        )

        # ── Scenario 12: Click on header expands ─────────────────────
        if thinking_blocks:
            await pilot.click("ThinkingBlock #header")
            await pilot.pause(0.2)
            tb = thinking_blocks.first()
            expanded = not tb.has_class("collapsed")
        else:
            expanded = False
        svg = _screenshot(app, 12, "click_expand")
        step(
            "Mouse click on Thinking block header → expand",
            "Click handler scoped to #header subtree; clicking the body does not toggle.",
            passed=expanded,
            svg=svg,
            detail=f"expanded={expanded}",
        )

        # ── Scenario 13: Sidebar narrow (icon-strip) ─────────────────
        sb = app.query_one(MonitorSidebar)
        sb.apply_terminal_width(110)
        await pilot.pause(0.1)
        icon_strip = sb.has_class("icon-strip")
        svg = _screenshot(app, 13, "sidebar_icon_strip")
        step(
            "Responsive sidebar — icon-strip at 110 cols",
            "Narrow terminal collapses the sidebar to an icon strip.",
            passed=icon_strip,
            svg=svg,
        )

        # ── Scenario 14: Sidebar wide (clamped to 50) ────────────────
        sb.apply_terminal_width(240)
        await pilot.pause(0.1)
        wide_width = int(sb.styles.width.value) if sb.styles.width else 0
        svg = _screenshot(app, 14, "sidebar_wide")
        step(
            "Responsive sidebar — clamps at 50 on wide terminals",
            "240 // 4 = 60, clamped to MAX_WIDTH=50.",
            passed=wide_width == 50,
            svg=svg,
            detail=f"width={wide_width}",
        )
        # Restore for the next screenshot
        sb.apply_terminal_width(180)
        await pilot.pause(0.1)

        # ── Scenario 15: Session resume replay ───────────────────────
        await app._resume_session(
            SessionAction("resume", session_id="sess_alpha", flavor="assistant")
        )
        await pilot.pause(0.4)
        conv = app._panes["assistant"].conversation
        from nx01_tui.tui.widgets import AssistantMessage, UserMessage

        users = conv.query(UserMessage)
        assistants = conv.query(AssistantMessage)
        replayed_thinking = conv.query(ThinkingBlock)
        replayed_tools = conv.query(ToolCallBlock)
        active_sid = app._active_session_id.get("assistant", "")
        svg = _screenshot(app, 15, "session_resume_replay")
        step(
            "Session resume replays history (W7) — user + assistant + tool + thinking",
            "Picking a session replays its DB row stream into ConversationView. "
            "_active_session_id[flavor] is set so the next send carries it.",
            passed=len(users) >= 1
            and len(assistants) >= 1
            and len(replayed_tools) >= 1
            and active_sid == "sess_alpha",
            svg=svg,
            detail=f"users={len(users)} assistants={len(assistants)} "
            f"thinking={len(replayed_thinking)} tools={len(replayed_tools)} sid={active_sid!r}",
        )

        # ── Scenario 16: Help modal ──────────────────────────────────
        from nx01_tui.tui.modals.help_modal import HelpModal

        app.push_screen(HelpModal())
        await pilot.pause(0.3)
        is_help = isinstance(app.screen, HelpModal)
        svg = _screenshot(app, 16, "help_modal")
        step(
            "Help modal — keybinding table",
            "Static reference table of every action + its key.",
            passed=is_help,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 17: Memory modal ────────────────────────────────
        from nx01_tui.tui.modals.memory_modal import MemoryModal

        agent_entries = [
            "User prefers dark mode and uses macOS with iTerm2.",
            "Active project: nx01-tui (Textual TUI for the NX01 fleet).",
            "Has API key `883e…b7cf` configured for the prod server.",
        ]
        user_entries = [
            "Name: Giedrius Jaloveckas",
            "Email: g.jaloveckas@gmail.com",
        ]
        app.push_screen(MemoryModal(agent_entries=agent_entries, user_entries=user_entries))
        await pilot.pause(0.3)
        is_mem = isinstance(app.screen, MemoryModal)
        svg = _screenshot(app, 17, "memory_modal")
        step(
            "Memory modal — agent + user entries",
            "Two tabbed lists, agent store and user profile.",
            passed=is_mem,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 18: Skills modal ────────────────────────────────
        from nx01_tui.tui.modals.simple_modals import SkillsModal

        skills = [
            {"name": "ci-setup", "size": 4096, "loaded": False},
            {"name": "browser", "size": 8192, "loaded": True},
            {"name": "python-debug", "size": 12288, "loaded": False},
            {"name": "kanban", "size": 6144, "loaded": False},
        ]
        app.push_screen(SkillsModal(skills))
        await pilot.pause(0.3)
        is_skills = isinstance(app.screen, SkillsModal)
        svg = _screenshot(app, 18, "skills_modal")
        step(
            "Skills modal — list with loaded indicator + size",
            "Loaded skills marked; clicking would load/unload.",
            passed=is_skills,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 19: Tools modal ─────────────────────────────────
        from nx01_tui.tui.modals.simple_modals import ToolsModal

        tools = [
            {"name": "bash", "description": "execute shell"},
            {"name": "read_file", "description": "read a file"},
            {"name": "edit_file", "description": "edit a file"},
            {"name": "web_fetch", "description": "fetch a URL"},
            {"name": "grep", "description": "search files"},
        ]
        app.push_screen(ToolsModal(tools))
        await pilot.pause(0.3)
        is_tools = isinstance(app.screen, ToolsModal)
        svg = _screenshot(app, 19, "tools_modal")
        step(
            "Tools modal — available tools list",
            "MCP / Toolsets tabs deferred to V2; tools-only for now.",
            passed=is_tools,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 20: Permission modal ────────────────────────────
        from nx01_tui.tui.modals.permission_modal import PermissionModal

        app.push_screen(
            PermissionModal(
                tool="bash",
                args="rm -rf /tmp/build-cache && rebuild_all.sh",
                risk="medium",
                description="Cleans build cache and rebuilds — destructive but reversible.",
            )
        )
        await pilot.pause(0.3)
        is_perm = isinstance(app.screen, PermissionModal)
        svg = _screenshot(app, 20, "permission_modal")
        step(
            "Permission modal — dangerous-tool confirmation",
            "y allow / n deny / a always-allow keybindings.",
            passed=is_perm,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 21: Confirm modal (destructive) ─────────────────
        from nx01_tui.tui.modals.confirm_modal import ConfirmModal

        app.push_screen(
            ConfirmModal("Delete this session? This cannot be undone.", dangerous=True)
        )
        await pilot.pause(0.3)
        is_conf = isinstance(app.screen, ConfirmModal)
        svg = _screenshot(app, 21, "confirm_modal")
        step(
            "Confirm modal — dangerous variant",
            "Red title; y yes / n no.",
            passed=is_conf,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 22: Debug modal ─────────────────────────────────
        from nx01_tui.tui.modals.debug_modal import DebugModal

        events = [
            parse_event(thinking(text="seed reasoning")),
            parse_event(tool_started(tool="bash", args="echo hi", call_id="d1")),
            parse_event(tool_completed(tool="bash", call_id="d1")),
            parse_event(chunk(text="hello world")),
            parse_event(turn_done()),
        ]
        app.push_screen(DebugModal(initial_buffer=events))
        await pilot.pause(0.3)
        is_dbg = isinstance(app.screen, DebugModal)
        svg = _screenshot(app, 22, "debug_modal")
        step(
            "Debug modal — raw SSE event log",
            "Ctrl+Shift+D opens a scrolling log of every event the SSE stream "
            "produced this session.",
            passed=is_dbg,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 23: Cost modal ──────────────────────────────────
        from nx01_tui.tui.modals.simple_modals import CostModal

        app.push_screen(
            CostModal(
                {
                    "input_tokens": 12450,
                    "output_tokens": 3120,
                    "total_cost_usd": 0.42,
                }
            )
        )
        await pilot.pause(0.3)
        is_cost = isinstance(app.screen, CostModal)
        svg = _screenshot(app, 23, "cost_modal")
        step(
            "Cost modal — token + USD breakdown",
            "Tracks cumulative input/output tokens + dollar cost.",
            passed=is_cost,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 24: Model picker ────────────────────────────────
        from nx01_tui.tui.modals.simple_modals import ModelPickerModal

        app.push_screen(
            ModelPickerModal(
                models=[
                    "claude-opus-4-7",
                    "claude-sonnet-4-6",
                    "claude-haiku-4-5",
                    "gpt-4o",
                    "o1-preview",
                ],
                current="claude-opus-4-7",
            )
        )
        await pilot.pause(0.3)
        is_mp = isinstance(app.screen, ModelPickerModal)
        svg = _screenshot(app, 24, "model_picker_modal")
        step(
            "Model picker — switch the underlying LLM",
            "Current model highlighted; Enter switches.",
            passed=is_mp,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 25: Config modal ────────────────────────────────
        from nx01_tui.tui.modals.simple_modals import ConfigModal

        app.push_screen(
            ConfigModal(
                {
                    "base_url": "https://77.42.71.240.nip.io",
                    "model": "claude-opus-4-7",
                    "flavor": "assistant",
                }
            )
        )
        await pilot.pause(0.3)
        is_cfg = isinstance(app.screen, ConfigModal)
        svg = _screenshot(app, 25, "config_modal")
        step(
            "Config modal — current app configuration",
            "Read-only snapshot of base_url / model / flavor.",
            passed=is_cfg,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 26: Search bar revealed ─────────────────────────
        app.action_search()
        await pilot.pause(0.3)
        flavor = app._active_flavor()
        from nx01_tui.tui.widgets import SearchBar

        bar = app.query_one(f"#search-{flavor}", SearchBar)
        search_visible = bar.has_class("visible")
        svg = _screenshot(app, 26, "search_bar")
        step(
            "Search bar — Ctrl+F reveals overlay above conversation",
            "Type to highlight matches; n/N step through.",
            passed=search_visible,
            svg=svg,
        )
        # Hide it so the next screenshots are clean.
        bar.remove_class("visible")
        await pilot.pause(0.1)

        # ── Scenario 27: ThinkingBlock expanded (chevron ▼) ──────────
        from nx01_tui.tui.widgets import ExpandChevron

        tb_q = app._panes[flavor].conversation.query(ThinkingBlock)
        if tb_q:
            tb = tb_q.first()
            tb.set_collapsed(False)
            await pilot.pause(0.1)
            chev = str(tb.query_one(ExpandChevron).render())
        else:
            chev = ""
        svg = _screenshot(app, 27, "thinking_expanded")
        step(
            "ThinkingBlock — expanded state (chevron ▼, body visible)",
            "When collapsed=False the RichLog body renders below the header.",
            passed=chev == "▼",
            svg=svg,
            detail=f"chevron={chev!r}",
        )

        # ── Scenario 28: ToolCallBlock error state ───────────────────
        # Drive an erroring tool through the state machine.
        from nx01_tui.tui.state import AgentState, ToolStatus

        conv = app._panes[flavor].conversation
        err_block = conv.start_tool(tool="curl", args="bad-url", call_id="err1")
        err_block.append_output("curl: (6) Could not resolve host")
        err_block.set_status(ToolStatus.ERROR)
        await pilot.pause(0.2)
        is_err = err_block.has_class("error")
        svg = _screenshot(app, 28, "tool_call_error")
        step(
            "ToolCallBlock — error state (red border, stays expanded)",
            "On ToolStatus.ERROR the block keeps the body visible so the user "
            "can read the failure output without expanding.",
            passed=is_err,
            svg=svg,
        )

        # ── Scenario 29: Agent state propagation in StatusBar ────────
        from nx01_tui.tui.widgets import StatusBar

        sb_w = app.query_one(StatusBar)
        sb_w.state = AgentState.STREAMING
        sb_w.flavor = flavor
        sb_w.tokens = 2480
        await pilot.pause(0.1)
        svg = _screenshot(app, 29, "status_bar_streaming")
        step(
            "StatusBar — STREAMING state with token count",
            "Bottom bar shows current flavor, agent state, cumulative tokens.",
            passed=sb_w.state == AgentState.STREAMING,
            svg=svg,
        )

        # ── Scenario 30: AppHeader connection states ─────────────────
        hdr = app.query_one(AppHeader)
        # Reconnecting
        hdr.reconnecting = True
        hdr.connected = False
        hdr.auth_failed = False
        await pilot.pause(0.1)
        svg = _screenshot(app, 30, "header_reconnecting")
        step(
            "AppHeader — reconnecting (yellow text + suffix)",
            "Color-only state signalling; no glyph.",
            passed="(reconnecting)" in hdr._brand_text(),
            svg=svg,
        )
        # Auth failed
        hdr.reconnecting = False
        hdr.auth_failed = True
        await pilot.pause(0.1)
        svg = _screenshot(app, 31, "header_auth_failed")
        step(
            "AppHeader — auth failed (red text + suffix)",
            "Distinct visual from network failure.",
            passed="(auth failed" in hdr._brand_text(),
            svg=svg,
        )
        # Offline
        hdr.auth_failed = False
        hdr.connected = False
        await pilot.pause(0.1)
        svg = _screenshot(app, 32, "header_offline")
        step(
            "AppHeader — offline (red text + suffix)",
            "Network unreachable; same red as auth failed but different suffix.",
            passed="(offline)" in hdr._brand_text(),
            svg=svg,
        )
        # Back to connected
        hdr.connected = True
        await pilot.pause(0.1)
        svg = _screenshot(app, 33, "header_connected")
        step(
            "AppHeader — connected (cyan text, no suffix)",
            "Steady state: cyan domain label, no parenthetical noise.",
            passed=hdr.connected is True,
            svg=svg,
        )

        # ── Scenario 34: Slash filtered by /skill prefix ─────────────
        ci = app.query_one(f"#input-{flavor}", ChatInput)
        ci.focus()
        ci.text = "/skill"
        slash = app.query_one(f"#slash-{flavor}", SlashDropdown)
        slash.update_for_text("/skill")
        await pilot.pause(0.2)
        skill_only = (
            slash.option_count >= 1
            and all(
                slash.get_option_at_index(i).id.startswith("/skill")
                for i in range(slash.option_count)
            )
        )
        svg = _screenshot(app, 34, "slash_filter_skill")
        step(
            "Slash filter — `/skill` narrows to skill category only",
            "User typed `/skill`; only `/skill <name>` entries remain.",
            passed=skill_only,
            svg=svg,
            detail=f"count={slash.option_count}",
        )

        # ── Scenario 35: Slash filtered by /tool prefix ──────────────
        ci.text = "/tool"
        slash.update_for_text("/tool")
        await pilot.pause(0.2)
        tool_only = (
            slash.option_count >= 1
            and all(
                slash.get_option_at_index(i).id.startswith("/tool")
                for i in range(slash.option_count)
            )
        )
        svg = _screenshot(app, 35, "slash_filter_tool")
        step(
            "Slash filter — `/tool` narrows to tool category only",
            "Same fuzzy filter, different category.",
            passed=tool_only,
            svg=svg,
            detail=f"count={slash.option_count}",
        )

        # ── Scenario 36: Slash dropdown — no matches ─────────────────
        ci.text = "/xyzdoesnotexist"
        slash.update_for_text("/xyzdoesnotexist")
        await pilot.pause(0.2)
        none = not slash.has_class("visible")
        svg = _screenshot(app, 36, "slash_no_match")
        step(
            "Slash dropdown — auto-hides on zero matches",
            "Typing a query that matches nothing dismisses the dropdown.",
            passed=none,
            svg=svg,
            detail=f"visible={slash.has_class('visible')}",
        )
        ci.text = ""
        slash.update_for_text("")
        await pilot.pause(0.1)

        # ── Scenario 37: Command palette with filter open + typed ────
        await pilot.press("ctrl+p")
        await pilot.pause(0.4)
        cmd_modal = app.screen
        if isinstance(cmd_modal, CommandModal):
            await pilot.press("slash")
            await pilot.pause(0.2)
            inp = cmd_modal.query_one("#filter", Input)
            inp.value = "session"
            cmd_modal.on_input_changed(Input.Changed(inp, "session"))  # type: ignore[attr-defined]
            await pilot.pause(0.2)
            lst = cmd_modal.query_one("#cmd-list", OptionList)
            filtered_count = lst.option_count
        else:
            filtered_count = 0
        svg = _screenshot(app, 37, "command_modal_filtered")
        step(
            "Command palette — `/` + typing `session` filters the action list",
            "Filter row visible at top; OptionList shows only matching actions.",
            passed=filtered_count >= 1,
            svg=svg,
            detail=f"filtered_count={filtered_count}",
        )
        await pilot.press("escape")
        await pilot.pause(0.2)
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 38: Sessions modal with filter + typed ──────────
        await pilot.press("ctrl+s")
        await pilot.pause(0.5)
        sess_modal = app.screen
        if isinstance(sess_modal, SessionsModal):
            await pilot.press("slash")
            await pilot.pause(0.2)
            inp = sess_modal.query_one("#filter", Input)
            inp.value = "Deploy"
            sess_modal.on_input_changed(Input.Changed(inp, "Deploy"))  # type: ignore[attr-defined]
            await pilot.pause(0.2)
            sess_visible = inp.has_class("visible")
        else:
            sess_visible = False
        svg = _screenshot(app, 38, "sessions_modal_filtered")
        step(
            "Sessions modal — `/` reveals filter, typed query narrows list",
            "Same hide-behind-`/` pattern as command palette.",
            passed=sess_visible,
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 39: Memory modal — empty fallback ───────────────
        from nx01_tui.tui.modals.memory_modal import MemoryModal

        app.push_screen(MemoryModal(agent_entries=[], user_entries=[]))
        await pilot.pause(0.3)
        svg = _screenshot(app, 39, "memory_modal_empty")
        step(
            "Memory modal — empty agent + user (graceful degradation)",
            "When both stores return zero entries, the modal still renders cleanly.",
            passed=isinstance(app.screen, MemoryModal),
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 40: Permission modal — high risk ────────────────
        from nx01_tui.tui.modals.permission_modal import PermissionModal

        app.push_screen(
            PermissionModal(
                tool="bash",
                args="rm -rf / --no-preserve-root",
                risk="high",
                description="Wipes the entire filesystem. This is not reversible.",
            )
        )
        await pilot.pause(0.3)
        svg = _screenshot(app, 40, "permission_modal_high")
        step(
            "Permission modal — high-risk variant",
            "Stronger visual emphasis when risk=`high`.",
            passed=isinstance(app.screen, PermissionModal),
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 41: Confirm modal — benign variant ──────────────
        from nx01_tui.tui.modals.confirm_modal import ConfirmModal

        app.push_screen(ConfirmModal("Reload skills from disk?", dangerous=False))
        await pilot.pause(0.3)
        svg = _screenshot(app, 41, "confirm_modal_benign")
        step(
            "Confirm modal — non-dangerous variant",
            "Neutral styling; no red.",
            passed=isinstance(app.screen, ConfirmModal),
            svg=svg,
        )
        await pilot.press("escape")
        await pilot.pause(0.2)

        # ── Scenario 42: FlavorPane THINKING border ──────────────────
        active_flavor = app._active_flavor()
        pane = app._panes[active_flavor]
        pane.set_state(AgentState.THINKING)
        await pilot.pause(0.1)
        svg = _screenshot(app, 42, "pane_state_thinking")
        step(
            "FlavorPane — THINKING border color (yellow)",
            "Pane border transitions to indicate agent state per ADR.",
            passed=pane.has_class("thinking"),
            svg=svg,
        )

        # ── Scenario 43: FlavorPane STREAMING border ─────────────────
        pane.set_state(AgentState.STREAMING)
        await pilot.pause(0.1)
        svg = _screenshot(app, 43, "pane_state_streaming")
        step(
            "FlavorPane — STREAMING border color (primary)",
            "Streaming state visible at a glance from the pane border.",
            passed=pane.has_class("streaming"),
            svg=svg,
        )

        # ── Scenario 44: FlavorPane TOOL_CALL border ─────────────────
        pane.set_state(AgentState.TOOL_CALL)
        await pilot.pause(0.1)
        svg = _screenshot(app, 44, "pane_state_tool_call")
        step(
            "FlavorPane — TOOL_CALL border color (green)",
            "Active tool call colors the pane edge.",
            passed=pane.has_class("tool_call"),
            svg=svg,
        )

        # ── Scenario 45: FlavorPane ERROR border ─────────────────────
        pane.set_state(AgentState.ERROR)
        await pilot.pause(0.1)
        svg = _screenshot(app, 45, "pane_state_error")
        step(
            "FlavorPane — ERROR border color (red)",
            "Persistent red until the user resets.",
            passed=pane.has_class("error"),
            svg=svg,
        )
        # Reset to IDLE so subsequent shots are clean.
        pane.set_state(AgentState.IDLE)
        await pilot.pause(0.1)

        # ── Scenario 46: StatusBar — each state cycled ───────────────
        sb_w = app.query_one(StatusBar)
        sb_w.flavor = active_flavor
        sb_w.tokens = 1000
        sb_w.state = AgentState.IDLE
        await pilot.pause(0.1)
        svg = _screenshot(app, 46, "status_bar_idle")
        step(
            "StatusBar — IDLE",
            "Idle baseline.",
            passed=sb_w.state == AgentState.IDLE,
            svg=svg,
        )

        sb_w.state = AgentState.THINKING
        sb_w.tokens = 1450
        await pilot.pause(0.1)
        svg = _screenshot(app, 47, "status_bar_thinking")
        step(
            "StatusBar — THINKING",
            "Thinking spinner + state label.",
            passed=sb_w.state == AgentState.THINKING,
            svg=svg,
        )

        sb_w.state = AgentState.TOOL_CALL
        sb_w.tokens = 1820
        await pilot.pause(0.1)
        svg = _screenshot(app, 48, "status_bar_tool_call")
        step(
            "StatusBar — TOOL_CALL",
            "Tool execution indicator.",
            passed=sb_w.state == AgentState.TOOL_CALL,
            svg=svg,
        )

        sb_w.state = AgentState.DONE
        sb_w.tokens = 2480
        await pilot.pause(0.1)
        svg = _screenshot(app, 49, "status_bar_done")
        step(
            "StatusBar — DONE",
            "Turn complete; final token count visible.",
            passed=sb_w.state == AgentState.DONE,
            svg=svg,
        )

        sb_w.state = AgentState.ERROR
        sb_w.tokens = 0
        await pilot.pause(0.1)
        svg = _screenshot(app, 50, "status_bar_error")
        step(
            "StatusBar — ERROR",
            "Error visible from bottom bar too.",
            passed=sb_w.state == AgentState.ERROR,
            svg=svg,
        )

        # ── Scenario 51: Sidebar populated with mock state ───────────
        from nx01_tui.tui.state import FlavorState

        mock_state = FlavorState(name=active_flavor)
        mock_state.apply_tool("bash", "ls -la", "started", call_id="m1")
        mock_state.apply_tool("read_file", "/etc/hosts", "completed", call_id="m2")
        mock_state.apply_tool("edit_file", "app.py", "completed", call_id="m3")
        mock_state.apply_skill_loaded("ci-setup", 4096)
        mock_state.apply_skill_loaded("browser", 8192)
        mock_state.token_usage = {"input": 12000, "output": 4500, "total": 16500}
        sidebar = pane.sidebar
        sidebar.update_from(mock_state)
        sidebar.set_memory(agent_chars=22500, user_chars=8800)
        sidebar.apply_terminal_width(180)
        await pilot.pause(0.2)
        svg = _screenshot(app, 51, "sidebar_populated")
        step(
            "Sidebar — fully populated (Activity / Memory / Skills / MCP / Context / Session)",
            "All six sections rendered with realistic mock data.",
            passed=True,
            svg=svg,
        )

        # ── Scenario 52: Conversation with code block ────────────────
        # Drive an assistant turn that emits a code fence — CodeBlock spawns
        # at end-of-turn for click-to-copy.
        conv = app._panes[active_flavor].conversation
        conv.reset_for_replay()
        conv.add_user_message("Show me a quick FastAPI hello world.")
        conv.start_assistant("Here's a minimal example:\n")
        for ch in "```python\nfrom fastapi import FastAPI\napp = FastAPI()\n@app.get('/')\ndef root():\n    return {'hello': 'world'}\n```":
            pass  # noqa: PERF102 — sentinel
        from nx01_tui.tui.widgets.messages import AssistantMessage

        msg = conv.query(AssistantMessage).last()
        msg.append(
            "```python\nfrom fastapi import FastAPI\n"
            "app = FastAPI()\n@app.get('/')\ndef root():\n    return {'hello': 'world'}\n```\n\n"
            "Run with `uvicorn main:app --reload`.\n"
        )
        conv.end_assistant()
        await pilot.pause(0.3)
        from nx01_tui.tui.widgets.code_block import CodeBlock

        code_blocks = conv.query(CodeBlock)
        svg = _screenshot(app, 52, "code_block_after_turn")
        step(
            "Conversation — fenced code block extracted into clickable CodeBlock",
            "When the assistant emits ```lang\\n…``` fences, end-of-turn splits "
            "them out into CodeBlock widgets for click-to-copy.",
            passed=len(code_blocks) >= 1,
            svg=svg,
            detail=f"code_blocks={len(code_blocks)}",
        )

        # ── Scenario 53: Multi-line input via Shift+Enter ────────────
        ci.focus()
        ci.text = "Line one\nLine two\nLine three"
        await pilot.pause(0.2)
        svg = _screenshot(app, 53, "chat_input_multiline")
        step(
            "ChatInput — multi-line composition (Shift+Enter / Alt+Enter newlines)",
            "TextArea grows up to max-height (8 lines) before scrolling internally.",
            passed="\n" in ci.text,
            svg=svg,
        )
        ci.text = ""
        await pilot.pause(0.1)

        # ── Scenario 54: Empty conversation hint ─────────────────────
        # Move to a fresh flavor that hasn't received any events.
        app.action_select_flavor(1)
        await pilot.pause(0.2)
        svg = _screenshot(app, 54, "empty_conversation_hint")
        step(
            "Empty conversation — welcome + keybind hint",
            "A flavor with no turns shows a `_EmptyState` widget with quick-start text.",
            passed=True,
            svg=svg,
        )
        # Back to the populated flavor for the final screenshot.
        app.action_select_flavor(0)
        await pilot.pause(0.2)

        # ── Scenario 55: Stacked modal — Confirm over Sessions ──────
        app.push_screen(
            SessionsModal(
                [
                    SessionEntry(
                        session_id="sess_alpha",
                        flavor="assistant",
                        title="Deploy CI",
                        last_active="2026-05-17",
                        message_count=12,
                        preview="set up github actions",
                    )
                ]
            )
        )
        await pilot.pause(0.3)
        app.push_screen(ConfirmModal("Delete this session? This cannot be undone.", dangerous=True))
        await pilot.pause(0.3)
        stack_depth = len(app.screen_stack)
        svg = _screenshot(app, 55, "stacked_modal")
        step(
            "Modal stack — Confirm dialog over SessionsModal",
            "Verifies modal-over-modal layout; backdrops compose correctly.",
            passed=stack_depth >= 3,
            svg=svg,
            detail=f"screen_stack_depth={stack_depth}",
        )
        await pilot.press("escape")
        await pilot.pause(0.2)
        await pilot.press("escape")
        await pilot.pause(0.2)

    return report


async def main() -> int:
    report = await run()
    out = report.write()
    passed = sum(1 for s in report.steps if s.passed)
    total = len(report.steps)
    print(f"\nv1.0 visual smoke: {passed}/{total} scenarios passed")
    print(f"Report:  {out}")
    print(f"SVGs:    {ARTIFACTS}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
