"""Probe: confirm the AssistantMessage Rich-markup-in-Markdown bug.

Item 24: AssistantMessage adds a `[bold $primary]── assistant ──[/]` prefix that
gets fed to Markdown. Rich/Textual Markdown does NOT interpret Rich tags — it
expects Markdown syntax. So the user sees literal `[bold $primary]── assistant ──[/]`.

This probe renders one assistant message and inspects the buffer.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nx01_tui.tui.app import Nx01App  # noqa: E402


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
    app = Nx01App("http://mock", api_key="t", flavors=["a"])
    _mock(app)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause(1.0)
        flavor = app._active_flavor()
        conv = app._panes[flavor].conversation

        # Add a user msg + an assistant msg
        conv.add_user_message("Hello assistant")
        am = conv.start_assistant("Hi there, the answer is **forty-two**.")
        conv.end_assistant()
        await pilot.pause(0.4)

        # Verify the divider is now a separate Rich-aware Static (not a
        # markdown-source prefix). The QA fix replaced the literal-markup leak.
        from textual.widgets import Static

        dividers = [s for s in am.query(Static) if "role-divider" in s.classes]
        if not dividers:
            failures.append(
                "AssistantMessage: no `.role-divider` Static mounted — "
                "post-fix divider component is missing"
            )

        app.save_screenshot(str(ROOT / "artifacts/v1-smoke/qa/probe_08_assistant_divider.svg"))

        # Inspect the rendered SVG content for literal "[bold $primary]"
        import re

        svg = (ROOT / "artifacts/v1-smoke/qa/probe_08_assistant_divider.svg").read_text()
        text_only = "".join(re.findall(r">([^<]+)<", svg)).replace("&#160;", " ")
        if "[bold $primary]" in text_only:
            failures.append("SVG: literal '[bold $primary]' visible on screen")
        if "[bold" in text_only or "[/]" in text_only:
            failures.append(
                "SVG: Rich-style markup tokens leak as literal text in AssistantMessage"
            )

    print("\n".join(failures) if failures else "OK: assistant divider OK")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
