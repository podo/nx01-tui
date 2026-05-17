"""Probe: ThinkingBlock chevron + spinner state machine.

Verifies item 11 (single indicator) + item 22 (chevron driven by reactive).

- Before done(): chevron hidden, spinner visible, set_collapsed(True) is no-op
- After done(): chevron visible (▶), spinner hidden, block has class .collapsed
- ToolCallBlock: collapsed reactive controls chevron via watch_collapsed
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.state import ToolStatus  # noqa: E402
from nx01_tui.tui.widgets.chevron import ExpandChevron  # noqa: E402
from nx01_tui.tui.widgets.spinner import SpinnerWidget, StarSpinner  # noqa: E402


def _mock(app):
    async def fake_get_flavors():
        return {"a": {"name": "a", "model": "m"}, "b": {"name": "b", "model": "m"}}

    async def fake_list_commands():
        return [{"name": "/help", "description": "h"}]

    async def fake_list_skills(flavor=None):
        return []

    async def fake_get_tools(flavor=None):
        return {"tools": []}

    app.client.get_flavors = fake_get_flavors
    app.client.list_commands = fake_list_commands
    app.client.list_skills = fake_list_skills
    app.client.get_tools = fake_get_tools


async def main() -> int:
    failures: list[str] = []
    app = Nx01App("http://mock", api_key="t", flavors=["a", "b"])
    _mock(app)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause(1.0)
        flavor = app._active_flavor()
        pane = app._panes[flavor]
        conv = pane.conversation

        # ── ThinkingBlock single-indicator handoff ──
        tb = conv.start_thinking()
        await pilot.pause(0.2)
        # During streaming: spinner visible, chevron hidden, set_collapsed(True) no-op
        spinner = tb.query_one(SpinnerWidget)
        chev = tb.query_one(ExpandChevron)
        if not spinner.display:
            failures.append("ThinkingBlock: spinner hidden while streaming (expected visible)")
        if chev.display:
            failures.append("ThinkingBlock: chevron visible while streaming (expected hidden)")
        # Try to collapse while still thinking
        tb.set_collapsed(True)
        if tb.collapsed:
            failures.append("ThinkingBlock: set_collapsed(True) while thinking should be a no-op")

        tb.append_chunk("hello world")
        tb.done()
        await pilot.pause(0.2)
        # After done: spinner hidden, chevron visible, block has .collapsed and .done classes
        if spinner.display:
            failures.append("ThinkingBlock: spinner still visible after done()")
        if not chev.display:
            failures.append("ThinkingBlock: chevron hidden after done() (expected visible)")
        if not tb.has_class("done"):
            failures.append("ThinkingBlock: .done class not added after done()")
        if not tb.has_class("collapsed"):
            failures.append("ThinkingBlock: .collapsed class not added after done()")
        # Chevron should now read ▶ (collapsed)
        glyph = str(chev.render())
        if glyph not in ("▶",):
            failures.append(f"ThinkingBlock: chevron glyph={glyph!r}, expected '▶'")
        # Re-toggle expanded
        tb.set_collapsed(False)
        await pilot.pause(0.1)
        if tb.collapsed:
            failures.append("ThinkingBlock: set_collapsed(False) after done did not expand")
        glyph = str(chev.render())
        if glyph != "▼":
            failures.append(f"ThinkingBlock: after expand chevron={glyph!r}, expected '▼'")

        # ── ToolCallBlock chevron via watcher ──
        tcb = conv.start_tool(tool="bash", args="ls", call_id="t1")
        await pilot.pause(0.2)
        tc_chev = tcb.query_one(ExpandChevron)
        # Initially collapsed=False (queued)
        tcb.collapsed = True
        await pilot.pause(0.1)
        if not tcb.has_class("collapsed"):
            failures.append("ToolCallBlock: watch_collapsed didn't add .collapsed class")
        if tc_chev.expanded:
            failures.append("ToolCallBlock: chevron.expanded=True when collapsed=True")
        tcb.collapsed = False
        await pilot.pause(0.1)
        if tcb.has_class("collapsed"):
            failures.append("ToolCallBlock: watch_collapsed didn't remove .collapsed class")
        if not tc_chev.expanded:
            failures.append("ToolCallBlock: chevron.expanded=False when collapsed=False")
        # Error path expands automatically
        tcb.set_status(ToolStatus.ERROR)
        await pilot.pause(0.1)
        if tcb.collapsed:
            failures.append("ToolCallBlock: ERROR did not auto-expand (collapsed still True)")
        glyph = str(tc_chev.render())
        if glyph != "▼":
            failures.append(f"ToolCallBlock: chevron={glyph!r} after ERROR, expected '▼'")
        # Done auto-collapses
        tcb2 = conv.start_tool(tool="bash", args="ls", call_id="t2")
        await pilot.pause(0.1)
        tcb2.set_status(ToolStatus.DONE)
        await pilot.pause(0.1)
        if not tcb2.collapsed:
            failures.append("ToolCallBlock: DONE did not auto-collapse")
        # StarSpinner: is it actually the SAME class as SpinnerWidget? (item 30)
        ss = tcb2.query_one(StarSpinner)
        if not isinstance(ss, StarSpinner):
            failures.append("ToolCallBlock: StarSpinner not present")

        app.save_screenshot(str(ROOT / "artifacts/v1-smoke/qa/probe_01_thinking_chevron.svg"))

    print("\n".join(failures) if failures else "OK: thinking + tool chevron probes PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
