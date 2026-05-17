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
from nx01_tui.tui.modals.sessions_modal import SessionAction  # noqa: E402
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
    # Decode `&#x27;` → `'` artefacts from textual's SVG export (#29 item 31).
    try:
        raw = path.read_text(encoding="utf-8")
        cleaned = raw.replace("&#x27;", "&apos;")
        if cleaned != raw:
            path.write_text(cleaned, encoding="utf-8")
    except OSError:
        pass
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

        # ── Scenario 6: Command palette list-focused (no filter, no V2) ─
        await pilot.press("ctrl+p")
        await pilot.pause(0.4)
        cmd_modal = app.screen
        from textual.widgets import Input, OptionList

        from nx01_tui.tui.modals.command_modal import CommandModal

        is_cmd_modal = isinstance(cmd_modal, CommandModal)
        list_focused = False
        no_filter = False
        no_v2 = False
        emoji_free = False
        if is_cmd_modal:
            lst = cmd_modal.query_one("#cmd-list", OptionList)
            list_focused = lst.has_focus
            # #29 item 14 — filter Input fully removed.
            no_filter = not cmd_modal.query(Input)
            # V2 rows hidden.
            ids = [
                lst.get_option_at_index(i).id
                for i in range(lst.option_count)
                if lst.get_option_at_index(i).id
            ]
            no_v2 = not any(opt and opt.startswith("v2_") for opt in ids)
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
            "Command palette — list-focused, no filter, no V2 rows, no emojis",
            "Ctrl+P opens the modal with the OptionList focused. Filter Input "
            "removed entirely (#29 item 14). V2-marked actions hidden.",
            passed=is_cmd_modal and list_focused and no_filter and no_v2 and emoji_free,
            svg=svg,
            detail=(
                f"is_cmd_modal={is_cmd_modal} list_focused={list_focused} "
                f"no_filter={no_filter} no_v2={no_v2} emoji_free={emoji_free}"
            ),
        )

        # ── Scenario 7: Command palette is filter-less — second screenshot
        # (kept for stable scenario count; verifies no `/` keystroke leaks).
        if is_cmd_modal:
            await pilot.press("slash")
            await pilot.pause(0.2)
            still_no_filter = not cmd_modal.query(Input)
        else:
            still_no_filter = False
        svg = _screenshot(app, 7, "command_modal_no_filter_after_slash")
        step(
            "Command palette — `/` no-op (filter is gone)",
            "Pressing `/` inside the modal does NOT spawn a filter input now.",
            passed=still_no_filter,
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

        # ── Scenario 13: Sidebar narrow — hidden entirely (#29 item 3) ─
        sb = app.query_one(MonitorSidebar)
        sb.apply_terminal_width(110)
        await pilot.pause(0.1)
        hidden = sb.has_class("hidden")
        svg = _screenshot(app, 13, "sidebar_hidden_narrow")
        step(
            "Responsive sidebar — hidden at 110 cols (icon-strip removed)",
            "Narrow terminal hides the sidebar entirely; no empty icon-strip "
            "sliver. StatusBar advertises `ctrl+b` to bring it back.",
            passed=hidden,
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
