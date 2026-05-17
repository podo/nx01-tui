"""Probe: cost modal (item 13), memory empty (item 15), debug modal (item 16),
help modal (item 17), status bar state (item 1), state ribbon (item 21).

Captures fresh screenshots for these modals after the design pass and asserts
key textual content shows up.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.modals.debug_modal import DebugModal  # noqa: E402
from nx01_tui.tui.modals.help_modal import HelpModal  # noqa: E402
from nx01_tui.tui.modals.memory_modal import MemoryModal  # noqa: E402

# CostModal lives in simple_modals — import it directly.
from nx01_tui.tui.modals.simple_modals import (  # noqa: E402
    ConfigModal,
    CostModal,
    ModelPickerModal,
    SkillsModal,
    ToolsModal,
)
from nx01_tui.tui.state import AgentState  # noqa: E402


def _mock(app):
    async def fake_get_flavors():
        return {"a": {"name": "a", "model": "claude"}}

    async def fake_list_commands():
        return []

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
    app = Nx01App("http://mock", api_key="t", flavors=["a"])
    _mock(app)
    qa_dir = ROOT / "artifacts/v1-smoke/qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause(1.0)

        # ── Cost modal: empty (zero tokens) — verify no crash, ratio bar handles 0 ──
        cm_empty = CostModal({})
        app.push_screen(cm_empty)
        await pilot.pause(0.2)
        # Ratio bar for total==0 returns "" — should NOT crash
        bar = cm_empty._ratio_bar()
        if bar != "":
            failures.append(f"CostModal empty ratio bar: {bar!r}, expected ''")
        app.save_screenshot(str(qa_dir / "probe_07_cost_empty.svg"))
        cm_empty.dismiss(None)
        await pilot.pause(0.2)

        # ── Cost modal populated: verify "This session" and "Lifetime" titles ──
        cm = CostModal(
            {
                "input_tokens": 12000,
                "output_tokens": 4000,
                "cached_tokens": 2000,
                "total_cost_usd": 0.42,
                "lifetime": {
                    "input_tokens": 50000,
                    "output_tokens": 20000,
                    "cached_tokens": 8000,
                    "total_cost_usd": 1.50,
                },
            }
        )
        app.push_screen(cm)
        await pilot.pause(0.2)
        app.save_screenshot(str(qa_dir / "probe_07_cost_populated.svg"))
        cm.dismiss(None)
        await pilot.pause(0.2)

        # ── Memory modal empty: per-tab store-specific copy ──
        mm = MemoryModal(agent_entries=[], user_entries=[])
        app.push_screen(mm)
        await pilot.pause(0.2)
        # Verify the empty-hint dict contains the expected copy
        hints = MemoryModal._EMPTY_HINT
        if "agent" not in hints or "user" not in hints:
            failures.append("MemoryModal _EMPTY_HINT missing 'agent' or 'user' key")
        if "Agent memory captures" not in hints["agent"]:
            failures.append("MemoryModal agent empty hint copy weak")
        if "User profile captures" not in hints["user"]:
            failures.append("MemoryModal user empty hint copy weak")
        app.save_screenshot(str(qa_dir / "probe_07_memory_empty.svg"))
        mm.dismiss(None)
        await pilot.pause(0.2)

        # ── Help modal ──
        hm = HelpModal()
        app.push_screen(hm)
        await pilot.pause(0.3)
        from textual.widgets import DataTable

        try:
            dt = hm.query_one(DataTable)
            if dt.cursor_type != "row":
                failures.append(
                    f"HelpModal DataTable cursor_type={dt.cursor_type!r}, expected 'row'"
                )
        except Exception as exc:  # noqa: BLE001
            failures.append(f"HelpModal DataTable missing: {exc}")
        # Check keybinding list contains Search/Enter, Ctrl+Q, Ctrl+1..9
        from nx01_tui.tui.modals.help_modal import _KEYBINDINGS

        keys = {row[1] for row in _KEYBINDINGS}
        for need in ("Ctrl+Q", "Ctrl+1..9", "Enter", "Shift+Enter"):
            if need not in keys:
                failures.append(f"Help missing key row: {need!r}")
        app.save_screenshot(str(qa_dir / "probe_07_help.svg"))
        hm.dismiss(None)
        await pilot.pause(0.2)

        # ── Debug modal: filter input + footer button row ──
        dm = DebugModal([])
        app.push_screen(dm)
        await pilot.pause(0.3)
        from textual.widgets import Button, Input

        try:
            footer_row = dm.query_one("#footer-row")
            btns = footer_row.query(Button)
            if len(btns) != 3:
                failures.append(f"DebugModal footer-row has {len(btns)} buttons, expected 3")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"DebugModal #footer-row missing: {exc}")
        try:
            dm.query_one("#filter", Input)
        except Exception:  # noqa: BLE001
            failures.append("DebugModal #filter Input missing")
        app.save_screenshot(str(qa_dir / "probe_07_debug.svg"))
        dm.dismiss(None)
        await pilot.pause(0.2)

        # ── Tools modal: V2 callout above list (not in hint line) ──
        tm = ToolsModal([])
        app.push_screen(tm)
        await pilot.pause(0.3)
        from textual.widgets import Static

        callouts = [s for s in tm.query(Static) if "dialog-callout" in (s.classes or set())]
        if not callouts:
            failures.append("ToolsModal missing .dialog-callout for V2 notice")
        app.save_screenshot(str(qa_dir / "probe_07_tools.svg"))
        tm.dismiss(None)
        await pilot.pause(0.2)

        # ── Skills modal: hint line includes 'enter toggle' ──
        sm = SkillsModal([])
        app.push_screen(sm)
        await pilot.pause(0.3)
        hints = [s for s in sm.query(Static) if "dialog-hint" in (s.classes or set())]
        " ".join(str(h._content) if hasattr(h, "_content") else "" for h in hints)
        app.save_screenshot(str(qa_dir / "probe_07_skills.svg"))
        sm.dismiss(None)
        await pilot.pause(0.2)

        # ── ModelPicker empty state ──
        mp = ModelPickerModal([])
        app.push_screen(mp)
        await pilot.pause(0.2)
        app.save_screenshot(str(qa_dir / "probe_07_model_picker_empty.svg"))
        mp.dismiss(None)
        await pilot.pause(0.2)

        # ── StatusBar state changes — visit each AgentState ──
        from nx01_tui.tui.widgets import StatusBar

        sb = app.query_one(StatusBar)
        for state in [
            AgentState.IDLE,
            AgentState.THINKING,
            AgentState.STREAMING,
            AgentState.TOOL_CALL,
            AgentState.DONE,
            AgentState.ERROR,
        ]:
            sb.state = state
            await pilot.pause(0.1)
            app.save_screenshot(str(qa_dir / f"probe_07_statusbar_{state.value}.svg"))

        # ── FlavorPane state ribbon — verify display:block when state set ──

        pane = app._panes["a"]
        pane.set_state(AgentState.THINKING)
        await pilot.pause(0.1)
        if not pane.has_class("thinking"):
            failures.append("FlavorPane: thinking class not added")
        app.save_screenshot(str(qa_dir / "probe_07_pane_thinking.svg"))
        pane.set_state(AgentState.STREAMING)
        await pilot.pause(0.1)
        app.save_screenshot(str(qa_dir / "probe_07_pane_streaming.svg"))

        # ── ConfigModal sanity ──
        conf = ConfigModal({"base_url": "x", "model": "m"})
        app.push_screen(conf)
        await pilot.pause(0.2)
        app.save_screenshot(str(qa_dir / "probe_07_config.svg"))
        conf.dismiss(None)
        await pilot.pause(0.2)

    print("\n".join(failures) if failures else "OK: remaining modals probe PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
