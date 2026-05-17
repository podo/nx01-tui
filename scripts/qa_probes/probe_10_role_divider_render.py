"""Probe 10: AssistantMessage / UserMessage role divider — RESOLVED check.

Mounts an AssistantMessage with a fenced code block, completes the turn,
and verifies:
  1. The visible SVG text contains `── assistant ──` (the divider).
  2. No literal `[bold $primary]` or `[/]` markup leaks (the old #24 bug).
  3. The `_buffer` attribute on AssistantMessage is preserved (conversation.py
     uses it for code-block extraction at end-of-turn).
  4. A CodeBlock child is mounted after `end_assistant` when a fenced block
     is present — i.e. the rewrite didn't break the extraction pathway.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.widgets.code_block import CodeBlock  # noqa: E402


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

        # Stream an assistant message containing a fenced python block.
        conv.add_user_message("show me code")
        am = conv.start_assistant("")
        conv.append_assistant("Here is the code:\n\n```python\nprint('hi')\n```\n")
        conv.end_assistant()
        await pilot.pause(0.5)

        # 1. _buffer survives — conversation.py:153 reads it post-fix.
        if not hasattr(am, "_buffer"):
            failures.append(
                "AssistantMessage._buffer attribute missing — breaks fenced-code extraction"
            )
        elif "```python" not in getattr(am, "_buffer", ""):
            failures.append(
                f"AssistantMessage._buffer doesn't contain streamed code fence: "
                f"{getattr(am, '_buffer', '')!r}"
            )

        # 2. CodeBlock mounted after end_assistant for the fenced block.
        code_blocks = list(conv.query(CodeBlock))
        if not code_blocks:
            failures.append(
                "No CodeBlock mounted after end_assistant — fenced-block extraction "
                "broken by AssistantMessage rewrite"
            )

        # 3. Inspect SVG for divider text + absence of literal markup.
        svg_path = ROOT / "artifacts/v1-smoke/qa/probe_10_role_divider.svg"
        app.save_screenshot(str(svg_path))
        svg = svg_path.read_text()
        text_only = "".join(re.findall(r">([^<]+)<", svg)).replace("&#160;", " ")

        if "── assistant ──" not in text_only:
            failures.append("SVG: '── assistant ──' divider text not visible (AssistantMessage)")
        if "── you ──" not in text_only:
            failures.append("SVG: '── you ──' divider text not visible (UserMessage)")
        if "[bold $primary]" in text_only:
            failures.append("SVG: literal '[bold $primary]' visible — markup leak regression")
        if "[bold]" in text_only or "[/]" in text_only:
            failures.append("SVG: Rich markup tokens '[bold]' / '[/]' visible as literal text")

        # 4. AssistantMessage child structure: must have role-divider Static.
        from textual.widgets import Static

        dividers = [s for s in am.query(Static) if "role-divider" in s.classes]
        if not dividers:
            failures.append("AssistantMessage missing `.role-divider` Static child")

        # 5. finalise() is now a no-op (per the rewrite). Re-call it; nothing
        # should crash and _buffer should remain stable.
        before_buf = getattr(am, "_buffer", "")
        am.finalise()
        if getattr(am, "_buffer", "") != before_buf:
            failures.append("AssistantMessage.finalise() altered _buffer (should be no-op)")

    print("\n".join(failures) if failures else "OK: role divider probe PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
