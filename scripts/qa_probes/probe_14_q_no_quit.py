"""Probe 14: plain `q` does NOT quit; types as char in ChatInput (#33).

Focuses ChatInput, presses `q`, asserts:
  1. `app._running` remains True.
  2. ChatInput.text contains `q` (the character was typed normally).
  3. No `q` key is present in Nx01App.BINDINGS (app-level binding removed).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.widgets import ChatInput  # noqa: E402


def _mock(app):
    async def fake_get_flavors():
        return {"a": {"name": "a", "model": "m"}}

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

    # Static check: no plain `q` in BINDINGS.
    plain_q = [b for b in Nx01App.BINDINGS if b.key.strip() == "q"]
    if plain_q:
        failures.append(
            f"Nx01App.BINDINGS still binds plain 'q': {[(b.key, b.action) for b in plain_q]}"
        )

    app = Nx01App("http://mock", api_key="t", flavors=["a"])
    _mock(app)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause(1.0)
        flavor = app._active_flavor()
        ci = app.query_one(f"#input-{flavor}", ChatInput)
        ci.focus()
        await pilot.pause(0.1)

        # 1. Press q. App must not quit, char must be typed.
        await pilot.press("q")
        await pilot.pause(0.2)

        if not app._running:
            failures.append("plain `q` quit the app — should be a typed char (#33)")
        if "q" not in ci.text:
            failures.append(f"plain `q` was not typed into ChatInput (text={ci.text!r})")

        # 2. Press several more q's — still no quit, accumulates.
        await pilot.press("q")
        await pilot.press("q")
        await pilot.pause(0.2)
        if ci.text.count("q") < 3:
            failures.append(f"successive `q` presses did not accumulate (text={ci.text!r})")

        app.save_screenshot(str(ROOT / "artifacts/v1-smoke/qa/probe_14_q_no_quit.svg"))

    print("\n".join(failures) if failures else "OK: q-no-quit probe PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
