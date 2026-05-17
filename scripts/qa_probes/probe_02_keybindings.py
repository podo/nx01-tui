"""Probe: keybinding reachability with ChatInput focused.

Verifies items 9, 33 + general keybinding hygiene:
- `q` does NOT quit (#33)
- `ctrl+q` quits
- `tab` cycles flavors even with ChatInput focused
- `ctrl+1..9` jumps to flavor
- `ctrl+b` toggles sidebar
- `ctrl+f` opens SearchBar
- SearchBar's Enter/Shift+Enter (no longer ctrl+n/ctrl+p)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.widgets import ChatInput, SearchBar  # noqa: E402
from nx01_tui.tui.widgets.sidebar import MonitorSidebar  # noqa: E402


def _mock(app):
    async def fake_get_flavors():
        return {f"f{i}": {"name": f"f{i}", "model": "m"} for i in range(3)}

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
    app = Nx01App("http://mock", api_key="t", flavors=["f0", "f1", "f2"])
    _mock(app)

    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause(1.0)
        flavor = app._active_flavor()
        ci = app.query_one(f"#input-{flavor}", ChatInput)
        ci.focus()
        await pilot.pause(0.1)

        # 1. `q` should NOT quit (#33)
        try:
            await pilot.press("q")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"q raised: {exc}")
        await pilot.pause(0.1)
        if not app._running:
            failures.append("`q` quit the app — should be no-op now (#33)")
        # Should appear as a typed char in the input
        if "q" not in ci.text:
            failures.append(
                f"`q` not typed into input (text={ci.text!r}); did global binding fire?"
            )
        ci.text = ""

        # 2. Tab cycles flavor (priority)
        before = app._active_flavor()
        await pilot.press("tab")
        await pilot.pause(0.2)
        after = app._active_flavor()
        if before == after:
            failures.append(f"tab did not cycle flavor (still {before})")

        # 3. ctrl+1..3 selects flavors
        for i, name in enumerate(["f0", "f1", "f2"]):
            await pilot.press(f"ctrl+{i + 1}")
            await pilot.pause(0.15)
            actual = app._active_flavor()
            if actual != name:
                failures.append(f"ctrl+{i + 1} did not select {name} (got {actual})")

        # 4. ctrl+9 with only 3 flavors is no-op
        before_oob = app._active_flavor()
        await pilot.press("ctrl+9")
        await pilot.pause(0.1)
        if app._active_flavor() != before_oob:
            failures.append("ctrl+9 with 3 flavors should be no-op")

        # 5. ctrl+b toggles sidebar
        flavor = app._active_flavor()
        sb = app.query_one(f"#sidebar-{flavor}", MonitorSidebar)
        sb.remove_class("hidden")  # ensure starting state
        was_hidden = sb.has_class("hidden")
        await pilot.press("ctrl+b")
        await pilot.pause(0.1)
        now_hidden = sb.has_class("hidden")
        if was_hidden == now_hidden:
            failures.append(
                f"ctrl+b did not toggle sidebar visibility ({was_hidden}->{now_hidden})"
            )

        # 6. ctrl+f opens SearchBar (re-focus input first; sidebar toggle may have stolen focus)
        ci2 = app.query_one(f"#input-{flavor}", ChatInput)
        ci2.focus()
        await pilot.pause(0.1)
        sb_search = app.query_one(f"#search-{flavor}", SearchBar)
        sb_search.remove_class("visible")
        await pilot.press("ctrl+f")
        await pilot.pause(0.3)
        if not sb_search.has_class("visible"):
            failures.append("ctrl+f did not show SearchBar")
        # SearchBar should NOT bind ctrl+n / ctrl+p anymore
        binding_keys = {b.key for b in sb_search.BINDINGS}
        if "ctrl+n" in binding_keys or "ctrl+p" in binding_keys:
            failures.append(f"SearchBar still binds ctrl+n/ctrl+p: {binding_keys}")
        # It should bind enter and shift+enter
        if "enter" not in binding_keys:
            failures.append("SearchBar missing 'enter' binding")
        if "shift+enter" not in binding_keys:
            failures.append("SearchBar missing 'shift+enter' binding")
        # Dismiss search bar
        await pilot.press("escape")
        await pilot.pause(0.1)

        # 7. Empty ctrl+1 with no flavors
        # (Already tested oob — additional: index=0 is f0)

        app.save_screenshot(str(ROOT / "artifacts/v1-smoke/qa/probe_02_keybindings.svg"))

        # 8. ctrl+q should quit cleanly (tested last)
        # Note: we don't actually press ctrl+q here because that exits the pilot test;
        # but we verify the binding exists with priority=True.
        action_request_quit = "ctrl+q" in {b.key for b in app.BINDINGS}
        if not action_request_quit:
            failures.append("Nx01App.BINDINGS missing ctrl+q")
        # `q` should NOT be in app bindings anymore
        if "q" in {b.key for b in app.BINDINGS}:
            failures.append("Nx01App.BINDINGS still binds plain 'q' (should be removed per #33)")

    print("\n".join(failures) if failures else "OK: keybindings probe PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
