"""Probe 16: priority bindings in App steal ctrl+c / ctrl+y from focused
modal Inputs and from DebugModal's own ctrl+y handler.

The QA fix added `priority=True` to ctrl+c (stop_generation) and
ctrl+y (yank_focused). Textual priority bindings on the App fire
regardless of which widget has focus, so:

  - Inside SessionsModal: focus its `#filter` Input, press ctrl+c.
    Expected (pre-fix): Input's selection-copy. Actual (post-fix):
    App.action_stop_generation fires.

  - Inside DebugModal: press ctrl+y. DebugModal binds ctrl+y to
    `yank_buffer` (Copy buffer) WITHOUT priority. App's ctrl+y is
    priority. Expected by author: yank_buffer. Actual: yank_focused.

Both are REGRESSIONS introduced by the priority=True landing.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from textual.widgets import Input  # noqa: E402

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.modals.debug_modal import DebugModal  # noqa: E402
from nx01_tui.tui.modals.sessions_modal import SessionEntry, SessionsModal  # noqa: E402


def _mock(app, *, notify_log: list[str], copy_log: list[str]):
    async def fake_get_flavors():
        return {"a": {"name": "a", "model": "m"}}

    app.client.get_flavors = fake_get_flavors
    app.client.list_commands = lambda: _ret([])
    app.client.list_skills = lambda flavor=None: _ret([])
    app.client.get_tools = lambda flavor=None: _ret({"tools": []})

    async def fake_abort(corr):
        notify_log.append(f"abort:{corr}")

    app.client.abort = fake_abort

    orig_notify = app.notify

    def cap_notify(message="", *args, **kwargs):
        notify_log.append(str(message))
        try:
            orig_notify(message, *args, **kwargs)
        except Exception:  # noqa: BLE001
            pass

    app.notify = cap_notify

    orig_copy = app.copy_to_clipboard

    def cap_copy(text):
        copy_log.append(text)
        try:
            orig_copy(text)
        except Exception:  # noqa: BLE001
            pass

    app.copy_to_clipboard = cap_copy


async def _ret(v):
    return v


async def main() -> int:
    findings: list[str] = []
    notify_log: list[str] = []
    copy_log: list[str] = []

    app = Nx01App("http://mock", api_key="t", flavors=["a"])
    _mock(app, notify_log=notify_log, copy_log=copy_log)

    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause(1.0)
        flavor = app._active_flavor()

        # ── Case A: SessionsModal filter Input → ctrl+c ────────────────
        sm = SessionsModal(
            [
                SessionEntry(session_id="s1", flavor=flavor, title="t1"),
                SessionEntry(session_id="s2", flavor=flavor, title="t2"),
            ]
        )
        app.push_screen(sm)
        await pilot.pause(0.4)
        try:
            filter_input = sm.query_one("#filter", Input)
        except Exception as exc:  # noqa: BLE001
            findings.append(f"SessionsModal #filter Input not found: {exc}")
            filter_input = None

        if filter_input is not None:
            filter_input.focus()
            await pilot.pause(0.1)
            # Type some text then attempt select-all-copy.
            filter_input.value = "test"
            await pilot.pause(0.1)
            # Seed a correlation id so stop_generation has work to do —
            # if the priority binding fires, abort:test-corr-id appears.
            app._current_correlation_id = "test-corr-id"
            notify_log.clear()
            await pilot.press("ctrl+c")
            await pilot.pause(0.4)
            if any("Stop sent" in m for m in notify_log) or any(
                "abort:test-corr-id" in m for m in notify_log
            ):
                findings.append(
                    "REGRESSION A: ctrl+c with SessionsModal filter Input "
                    "focused fires App.action_stop_generation (priority=True), "
                    "stealing Input's selection-copy. notify_log=" + repr(notify_log[-3:])
                )
        sm.dismiss(None)
        await pilot.pause(0.3)

        # ── Case B: DebugModal → ctrl+y ────────────────────────────────
        dm = DebugModal([])
        app.push_screen(dm)
        await pilot.pause(0.4)
        # Seed a chunk so App.action_yank_focused has something to copy —
        # if priority fires, copy_log will contain that chunk text.
        state = app._states.get(flavor)
        if state is not None:
            state.messages.append({"type": "chunk", "text": "MARKER_FROM_APP_YANK_FOCUSED"})
        copy_log.clear()
        notify_log.clear()
        await pilot.press("ctrl+y")
        await pilot.pause(0.4)
        if any("MARKER_FROM_APP_YANK_FOCUSED" in c for c in copy_log):
            findings.append(
                "REGRESSION B: ctrl+y inside DebugModal fires App.action_yank_focused "
                "(priority=True), stealing DebugModal's own ctrl+y → yank_buffer handler. "
                "copy_log contains the marker."
            )
        dm.dismiss(None)
        await pilot.pause(0.3)

    if findings:
        print("\n".join(findings))
    else:
        print("OK: no priority-binding modal-steal regressions observed")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
