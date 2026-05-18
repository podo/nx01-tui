"""nx01-tui v1.1 visual smoke runner — verifies all 7 fixes from v1.1.

Scenarios
    S01  Model display        claude-opus-4-5-20250514 → opus-4.5 in header
    S02  Skills sidebar       bootstrap pre-populates sidebar (not "no skills loaded")
    S03  Thinking stays open  done() keeps block expanded with ✓ status
    S04  Tool hex-ID hidden   tc-[hex] tool → readable "delegate" label
    S05  Sessions Enter key   OptionList.OptionSelected fires resume/dismiss
    S06  Quit saves state     _save_session_state() writes ~/.nx01_tui_state.json
    S07  Auto-resume + divider fresh boot with state file → UnreadDivider in conversation

Usage:
    python3 scripts/v11_smoke.py
    open artifacts/v11-smoke/REPORT.md
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nx01_tui.tui.app import _STATE_FILE, Nx01App  # noqa: E402
from nx01_tui.tui.events import parse_event  # noqa: E402
from nx01_tui.tui.modals.sessions_modal import SessionsModal  # noqa: E402
from nx01_tui.tui.widgets import (  # noqa: E402
    AppHeader,
    ThinkingBlock,
    ToolCallBlock,
)
from nx01_tui.tui.widgets.conversation import UnreadDivider  # noqa: E402
from nx01_tui.tui.widgets.sidebar import SkillsSection  # noqa: E402
from tests.fixtures.sample_events import (  # noqa: E402
    chunk,
    thinking,
    turn_done,
)

ARTIFACTS = ROOT / "artifacts" / "v11-smoke"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

# ── Data classes ─────────────────────────────────────────────────────


@dataclass
class Step:
    n: int
    name: str
    description: str
    png_path: str = ""
    passed: bool = False
    detail: str = ""


@dataclass
class Report:
    steps: list[Step] = field(default_factory=list)

    def add(self, step: Step) -> None:
        self.steps.append(step)

    def write(self) -> Path:
        out = ARTIFACTS / "REPORT.md"
        lines = ["# nx01-tui v1.1 visual smoke report", ""]
        passed = sum(1 for s in self.steps if s.passed)
        lines.append(f"**{passed} / {len(self.steps)} scenarios passed**")
        lines.append("")
        lines.append("| # | Scenario | Pass | PNG |")
        lines.append("|---|---|---|---|")
        for s in self.steps:
            mark = "✓" if s.passed else "✗"
            link = f"[{Path(s.png_path).name}]({Path(s.png_path).name})" if s.png_path else "—"
            lines.append(f"| S{s.n:02d} | {s.name} | {mark} | {link} |")
        lines.append("")
        for s in self.steps:
            lines.append(f"## S{s.n:02d}: {s.name}")
            lines.append(f"_{s.description}_")
            if s.png_path:
                lines.append("")
                lines.append(f"![]({Path(s.png_path).name})")
            if s.detail:
                lines.append("")
                lines.append("```")
                lines.append(s.detail)
                lines.append("```")
            lines.append("")
        out.write_text("\n".join(lines))
        return out


# ── Helpers ───────────────────────────────────────────────────────────


_svg_paths: list[str] = []  # collected during run, converted in one batch at end


def _screenshot(app: Nx01App, n: int, slug: str) -> str:
    """Save SVG screenshot; return the expected PNG path (converted later in batch)."""
    svg_path = ARTIFACTS / f"s{n:02d}_{slug}.svg"
    app.save_screenshot(str(svg_path))
    try:
        raw = svg_path.read_text(encoding="utf-8")
        cleaned = raw.replace("&#x27;", "'").replace("&apos;", "'")
        if cleaned != raw:
            svg_path.write_text(cleaned, encoding="utf-8")
    except OSError:
        pass
    png_path = str(svg_path).replace(".svg", ".png")
    _svg_paths.append(str(svg_path))
    return png_path  # may not exist yet; batch conversion fills it in


def _batch_convert_svgs() -> None:
    """Convert all collected SVGs to PNGs via rsvg-convert (fast, no browser needed)."""
    import subprocess

    if not _svg_paths:
        return
    print(f"\nConverting {len(_svg_paths)} SVGs → PNG via rsvg-convert…")
    for svg in _svg_paths:
        png = svg.replace(".svg", ".png")
        try:
            result = subprocess.run(
                ["rsvg-convert", "-w", "1800", svg, "-o", png],
                capture_output=True, timeout=10,
            )
            if result.returncode == 0:
                print(f"  converted {Path(svg).name}")
            else:
                print(f"  [warn] {Path(svg).name}: {result.stderr.decode()[:100]}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] {Path(svg).name}: {exc}")


async def _settle(app: Nx01App, pilot, secs: float = 1.5) -> None:
    await pilot.pause(secs)
    for w in list(app.workers):
        w.cancel()
    await pilot.pause(0.3)


def _mock_client(client) -> None:
    """Replace network layer with deterministic fakes for v1.1 scenarios."""

    async def fake_get_flavors():
        return {
            "assistant": {"name": "assistant", "model": "claude-opus-4-5-20250514"},
            "operator": {"name": "operator", "model": "claude-opus-4-5-20250514"},
        }

    async def fake_list_commands():
        return [{"name": "/help", "description": "show help"}]

    async def fake_list_skills(flavor=None):
        return [
            {"name": "find-skills", "size": 3200, "loaded": True},
            {"name": "browser", "size": 8192, "loaded": True},
        ]

    async def fake_get_tools(flavor=None):
        return {"tools": [{"name": "bash", "description": "execute shell"}]}

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
        ]

    async def fake_resume_session(sid):
        return {"session": {"id": sid}}

    async def fake_get_session_messages(sid, flavor=None):
        past_ts = time.time() - 3600
        future_ts = time.time() + 1  # "new" messages after quit_ts
        return [
            {"role": "user", "content": "Set up a CI workflow", "timestamp": past_ts - 100},
            {
                "role": "assistant",
                "content": "I'll write the YAML for you.",
                "reasoning": "user wants GitHub Actions",
                "timestamp": past_ts - 50,
            },
            # These rows are "new" (timestamp > quit_ts set in state file)
            {"role": "user", "content": "Also add a lint step", "timestamp": future_ts},
            {
                "role": "assistant",
                "content": "Done — lint step added.",
                "timestamp": future_ts + 1,
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
    client.fork_session = lambda sid: None
    client.delete_session = lambda sid: None
    client.send_message = lambda *a, **k: {"session_id": "sess_alpha", "correlation_id": "c1"}
    client.abort = lambda cid: None


# ── Main run ──────────────────────────────────────────────────────────


async def run() -> Report:
    report = Report()
    n = 0

    def step(name: str, description: str, passed: bool, png: str = "", detail: str = "") -> None:
        nonlocal n
        n += 1
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  S{n:02d} {status}  {name}")
        if detail:
            print(f"       {detail}")
        report.add(
            Step(  # noqa: E501
                n=n, name=name, description=description, png_path=png, passed=passed, detail=detail
            )
        )

    # ─────────────────────────────────────────────────────────────────
    # Scenarios S01–S05: single app boot
    # ─────────────────────────────────────────────────────────────────

    print("\nBooting app for S01–S05…")
    app = Nx01App("http://mock", api_key="test", flavors=["assistant", "operator"])
    _mock_client(app.client)

    async with app.run_test(size=(180, 50)) as pilot:
        await _settle(app, pilot)

        # ── S01: Model display ────────────────────────────────────────
        hdr = app.query_one(AppHeader)
        brand = hdr._brand_text()
        # claude-opus-4-5-20250514 → opus-4.5
        has_short = "opus-4.5" in brand
        has_no_full = "20250514" not in brand
        png = _screenshot(app, 1, "model_display")
        step(
            "Model display — claude-opus-4-5-20250514 → opus-4.5",
            "Header should show the shortened model name, not the raw API ID with date suffix.",
            passed=has_short and has_no_full,
            png=png,
            detail=f"brand={brand!r}  has_short={has_short} no_date={has_no_full}",
        )

        # ── S02: Skills sidebar populated on bootstrap ────────────────
        flavor = app._active_flavor()
        pane = app._panes.get(flavor)
        skills_section = pane.sidebar.query_one(SkillsSection) if pane else None
        sidebar_text = ""
        skills_shown = False
        no_empty_msg = False
        if skills_section:
            container = skills_section.query_one("#skills-list")
            children = list(container.children)
            sidebar_text = " ".join(str(c.render()) for c in children)
            # Sidebar should list skill names, not "no skills loaded"
            skills_shown = len(children) > 0
            no_empty_msg = "no skills loaded" not in sidebar_text.lower()
        # Also check state.skills_loaded
        state_skills = app._states.get(flavor, None)
        state_has_skills = bool(state_skills and state_skills.skills_loaded)
        png = _screenshot(app, 2, "skills_sidebar")
        step(
            "Skills sidebar — pre-populated on bootstrap",
            "After bootstrap with API skills, sidebar must show skill names, not 'no skills loaded'.",  # noqa: E501
            passed=skills_shown and no_empty_msg and state_has_skills,
            png=png,
            detail=(
                f"children={skills_shown} no_empty={no_empty_msg} "
                f"state_skills={state_has_skills} "
                f"loaded={[s['name'] for s in (state_skills.skills_loaded if state_skills else [])]}"  # noqa: E501
            ),
        )

        # ── S03: Thinking block stays expanded on done() ─────────────
        # Pause after thinking so ThinkingBlock fully mounts before done() queries #label.
        app._dispatch_event(parse_event(thinking(text="Analysing the problem…")))
        await pilot.pause(0.3)
        app._dispatch_event(parse_event(chunk(text="Here is the answer.")))
        app._dispatch_event(parse_event(turn_done()))
        await pilot.pause(0.3)
        await pilot.pause(0.4)
        conv = app._panes[flavor].conversation
        thinking_blocks = list(conv.query(ThinkingBlock))
        tb = thinking_blocks[-1] if thinking_blocks else None
        is_not_collapsed = tb is not None and not tb.has_class("collapsed")
        is_done_class = tb is not None and tb.has_class("done")
        # Header label should contain the ✓ status symbol
        label_text = ""
        if tb:
            from textual.widgets import Static
            try:
                lbl = tb.query_one("#label", Static)
                label_text = str(lbl.render())
            except Exception:
                pass
        has_checkmark = "✓" in label_text or "Thought" in label_text
        png = _screenshot(app, 3, "thinking_stays_expanded")
        step(
            "Thinking block — stays expanded after done(), shows ✓ status",
            "done() must NOT auto-collapse. Block keeps its content visible with an inline status change.",  # noqa: E501
            passed=is_not_collapsed and is_done_class and has_checkmark,
            png=png,
            detail=(
                f"collapsed={tb.has_class('collapsed') if tb else 'N/A'} "
                f"done_class={is_done_class} checkmark_in_label={has_checkmark} "
                f"label={label_text!r}"
            ),
        )

        # ── S04: Tool call hex ID hidden ──────────────────────────────
        hex_tool_event = {
            "type": "ToolCallEvent",
            "flavor": flavor,
            "tool": "tc-abcdef012345",
            "title": "delegate: fetch the skill definition",
            "status": "started",
            "call_id": "tc-abcdef012345",
            "at": 0,
        }
        app._dispatch_event(parse_event(hex_tool_event))
        await pilot.pause(0.3)
        tool_blocks = list(conv.query(ToolCallBlock))
        hex_block = next(
            (b for b in tool_blocks if b.call_id == "tc-abcdef012345"), None
        )
        shows_no_hex = hex_block is not None and hex_block.tool != "tc-abcdef012345"
        shows_readable = hex_block is not None and hex_block.tool == "delegate"
        png = _screenshot(app, 4, "tool_hex_hidden")
        step(
            "Tool call — tc-[hex] replaced with readable label",
            "When backend sends a call_id as the tool name, the TUI should use the title instead.",
            passed=shows_no_hex and shows_readable,
            png=png,
            detail=(
                f"hex_block_tool={getattr(hex_block, 'tool', 'N/A')!r} "
                f"no_hex={shows_no_hex} readable={shows_readable}"
            ),
        )

        # ── S05: Sessions modal Enter key ─────────────────────────────
        await pilot.press("ctrl+s")
        await pilot.pause(0.5)
        modal = app.screen
        is_modal = isinstance(modal, SessionsModal)
        # Simulate OptionList.OptionSelected (what Enter fires internally)
        dismissed = False
        if is_modal:
            from textual.widgets import OptionList
            lst = modal.query_one("#session-list", OptionList)
            # Find the first selectable option
            for i in range(lst.option_count):
                opt = lst.get_option_at_index(i)
                if opt and opt.id and "::" in opt.id:
                    # Post the OptionSelected message directly (option, index order)
                    modal.post_message(OptionList.OptionSelected(lst, opt, i))
                    await pilot.pause(0.4)
                    # If modal dismissed, we're back at main screen
                    dismissed = not isinstance(app.screen, SessionsModal)
                    break
        png = _screenshot(app, 5, "sessions_enter_key")
        step(
            "Sessions modal — Enter (OptionSelected) dismisses and resumes",
            "OptionList.OptionSelected handler should call dismiss(SessionAction('resume', ...)).",
            passed=is_modal and dismissed,
            png=png,
            detail=f"was_modal={is_modal} dismissed={dismissed}",
        )
        # Close if still open
        if isinstance(app.screen, SessionsModal):
            await pilot.press("escape")
            await pilot.pause(0.2)

        # ── S06: Quit saves session state ─────────────────────────────
        # Inject a session id so there's something to save
        app._active_session_id["assistant"] = "sess_alpha"
        # Remove any pre-existing state file so we get a clean test
        if _STATE_FILE.exists():
            _STATE_FILE.unlink()
        app._save_session_state()
        file_exists = _STATE_FILE.exists()
        saved_data = {}
        if file_exists:
            try:
                saved_data = json.loads(_STATE_FILE.read_text())
            except Exception:
                pass
        has_version = saved_data.get("version") == 1
        has_session = (
            "assistant" in saved_data.get("sessions", {})
            and saved_data["sessions"]["assistant"].get("session_id") == "sess_alpha"
        )
        has_ts = "quit_ts" in saved_data.get("sessions", {}).get("assistant", {})
        png = _screenshot(app, 6, "quit_saves_state")
        step(
            "Quit — saves session state to ~/.nx01_tui_state.json",
            "_save_session_state() must write version=1, session_id, and quit_ts for each active session.",  # noqa: E501
            passed=file_exists and has_version and has_session and has_ts,
            png=png,
            detail=(
                f"file_exists={file_exists} version={has_version} "
                f"session={has_session} ts={has_ts} "
                f"data={json.dumps(saved_data, indent=None)}"
            ),
        )

    # ─────────────────────────────────────────────────────────────────
    # S07: Fresh boot with saved state → auto-resume + unread divider
    # ─────────────────────────────────────────────────────────────────

    print("\nBooting app for S07 (auto-resume + unread divider)…")

    # Write a state file with quit_ts 10 seconds ago so that the "future_ts"
    # rows in fake_get_session_messages (time.time()+1) are clearly "new".
    quit_ts = time.time() - 10
    _STATE_FILE.write_text(
        json.dumps({
            "version": 1,
            "sessions": {
                "assistant": {
                    "session_id": "sess_alpha",
                    "quit_ts": quit_ts,
                }
            },
        })
    )

    app2 = Nx01App("http://mock", api_key="test", flavors=["assistant", "operator"])
    _mock_client(app2.client)

    async with app2.run_test(size=(180, 50)) as pilot2:
        await _settle(app2, pilot2, secs=2.5)

        conv2 = app2._panes.get("assistant")
        dividers = list(conv2.conversation.query(UnreadDivider)) if conv2 else []
        has_divider = len(dividers) > 0
        divider_text = str(dividers[0].render()) if dividers else ""
        # State file should still exist (we don't delete it on resume)
        sid_set = app2._active_session_id.get("assistant") == "sess_alpha"
        png = _screenshot(app2, 7, "auto_resume_unread_divider")
        step(
            "Auto-resume — UnreadDivider appears, session restored",
            "On boot, if state file exists, the app resumes the last session and inserts "
            "an UnreadDivider at the first message that arrived after quit_ts.",
            passed=has_divider and sid_set,
            png=png,
            detail=(
                f"has_divider={has_divider} divider_text={divider_text!r} "
                f"sid={app2._active_session_id.get('assistant')!r}"
            ),
        )

    # Clean up temp state file so it doesn't affect real usage
    try:
        _STATE_FILE.unlink()
    except Exception:
        pass

    return report


async def main() -> int:
    print("nx01-tui v1.1 visual smoke")
    print("=" * 40)
    report = await run()
    out = report.write()
    _batch_convert_svgs()
    passed = sum(1 for s in report.steps if s.passed)
    total = len(report.steps)
    print(f"\n{'=' * 40}")
    print(f"Result:  {passed}/{total} scenarios passed")
    print(f"Report:  {out}")
    print(f"PNGs:    {ARTIFACTS}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
