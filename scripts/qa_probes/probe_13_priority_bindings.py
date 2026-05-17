"""Probe 13: Priority bindings reach App handlers even from focused ChatInput.

The earlier probe_02 was too lenient: it focused ChatInput before some
asserts but skipped the most damning checks. This probe drives every
priority shortcut and verifies its observable side effect, while also
hunting for regressions caused by the same `priority=True` change:

  - `ctrl+f`         → SearchBar acquires `.visible`
  - `ctrl+k`         → SkillsModal pushed onto screen stack
  - `ctrl+c`         → abort posted (action_stop_generation; we set
                        `_current_correlation_id` and verify the worker
                        was scheduled by checking the notify text)
  - `ctrl+y`         → action_yank_focused (we seed a chunk message and
                        verify the clipboard helper was invoked)
  - `ctrl+shift+y`   → action_yank_last_code (we seed a chunk containing
                        a fenced block and verify the helper was invoked)

Regression hunt (REGRESSED column in the reverify):
  - When focus is on a non-Input widget, plain typed characters should
    NOT accidentally type a `\\x03` into ChatInput after ctrl+c.
  - After ctrl+c, ChatInput's text must remain empty (no char inserted).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.modals.simple_modals import SkillsModal  # noqa: E402
from nx01_tui.tui.widgets import ChatInput, SearchBar  # noqa: E402


def _mock(app, *, copy_log: list[str], notify_log: list[str]):
    async def fake_get_flavors():
        return {"a": {"name": "a", "model": "m"}}

    async def fake_list_commands():
        return []

    async def fake_list_skills(flavor=None):
        return []

    async def fake_get_tools(flavor=None):
        return {"tools": []}

    async def fake_abort(correlation_id):
        copy_log.append(f"abort:{correlation_id}")

    app.client.get_flavors = fake_get_flavors
    app.client.list_commands = fake_list_commands
    app.client.list_skills = fake_list_skills
    app.client.get_tools = fake_get_tools
    app.client.abort = fake_abort

    # Hook copy_to_clipboard + notify to capture side effects.
    orig_copy = app.copy_to_clipboard

    def capture_copy(text):
        copy_log.append(text)
        try:
            orig_copy(text)
        except Exception:  # noqa: BLE001
            pass

    app.copy_to_clipboard = capture_copy

    orig_notify = app.notify

    def capture_notify(message="", *args, **kwargs):
        notify_log.append(str(message))
        try:
            orig_notify(message, *args, **kwargs)
        except Exception:  # noqa: BLE001
            pass

    app.notify = capture_notify


async def main() -> int:
    failures: list[str] = []
    copy_log: list[str] = []
    notify_log: list[str] = []
    app = Nx01App("http://mock", api_key="t", flavors=["a"])
    _mock(app, copy_log=copy_log, notify_log=notify_log)

    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause(1.0)
        flavor = app._active_flavor()
        ci = app.query_one(f"#input-{flavor}", ChatInput)
        ci.focus()
        await pilot.pause(0.1)

        # ── 1. ctrl+f → SearchBar visible ──────────────────────────────
        bar = app.query_one(f"#search-{flavor}", SearchBar)
        bar.remove_class("visible")
        ci.focus()
        await pilot.pause(0.1)
        await pilot.press("ctrl+f")
        await pilot.pause(0.3)
        if not bar.has_class("visible"):
            failures.append("ctrl+f from ChatInput focus did NOT show SearchBar")
        # ChatInput text must remain empty — no `\x06` typed.
        if ci.text:
            failures.append(f"ctrl+f leaked into ChatInput text: {ci.text!r}")
        # Dismiss the search bar so subsequent ctrl+f tests are clean.
        bar.remove_class("visible")
        ci.focus()
        await pilot.pause(0.1)

        # ── 2. ctrl+k → SkillsModal pushed ─────────────────────────────
        ci.focus()
        await pilot.press("ctrl+k")
        await pilot.pause(0.4)
        top = app.screen_stack[-1] if len(app.screen_stack) > 1 else None
        if not isinstance(top, SkillsModal):
            failures.append(
                f"ctrl+k did NOT push SkillsModal — top of stack = {type(top).__name__}"
            )
        # Dismiss the modal so subsequent tests run against base app screen.
        if isinstance(top, SkillsModal):
            top.dismiss(None)
            await pilot.pause(0.3)
        ci.focus()
        await pilot.pause(0.1)
        if ci.text:
            failures.append(f"ctrl+k leaked into ChatInput text: {ci.text!r}")

        # ── 3. ctrl+c → action_stop_generation ─────────────────────────
        # Seed a correlation id so the abort branch fires.
        app._current_correlation_id = "test-corr-id"
        copy_log.clear()
        notify_log.clear()
        ci.focus()
        await pilot.pause(0.1)
        await pilot.press("ctrl+c")
        await pilot.pause(0.5)
        if not any("Stop sent" in m for m in notify_log):
            failures.append(
                f"ctrl+c did NOT trigger action_stop_generation — notify log: {notify_log}"
            )
        if ci.text:
            failures.append(f"ctrl+c leaked a typed character into ChatInput: {ci.text!r}")

        # ── 4. ctrl+y → action_yank_focused ────────────────────────────
        state = app._states[flavor]
        state.messages.append({"type": "chunk", "text": "Hello world"})
        copy_log.clear()
        notify_log.clear()
        ci.focus()
        await pilot.pause(0.1)
        await pilot.press("ctrl+y")
        await pilot.pause(0.3)
        if "Hello world" not in copy_log:
            failures.append(f"ctrl+y did NOT yank focused chunk — copy_log={copy_log}")
        if ci.text:
            failures.append(f"ctrl+y leaked a typed character into ChatInput: {ci.text!r}")

        # ── 5. ctrl+shift+y → action_yank_last_code ────────────────────
        state.messages.append(
            {
                "type": "chunk",
                "text": "see code below\n```python\nprint('xyz')\n```\n",
            }
        )
        copy_log.clear()
        notify_log.clear()
        ci.focus()
        await pilot.pause(0.1)
        await pilot.press("ctrl+shift+y")
        await pilot.pause(0.3)
        # _extract_last_code_block returns the contents; we expect "print('xyz')".
        if not any("print('xyz')" in c for c in copy_log):
            failures.append(f"ctrl+shift+y did NOT yank last code block — copy_log={copy_log}")
        if ci.text:
            failures.append(f"ctrl+shift+y leaked a typed character into ChatInput: {ci.text!r}")

        app.save_screenshot(str(ROOT / "artifacts/v1-smoke/qa/probe_13_priority.svg"))

    print("\n".join(failures) if failures else "OK: priority bindings probe PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
