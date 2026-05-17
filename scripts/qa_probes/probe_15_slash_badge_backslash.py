"""Probe 15: SlashDropdown badge regression — literal `\\]` artefact.

The QA fix for #12 replaced the nested-Rich-tag bracket hack with a raw
string using `\\[` and `\\]` escapes (slash_dropdown.py:161). In Rich
markup, `\\[` escapes a literal `[` (since `[` opens a tag), but `\\]`
is NOT a recognised escape — Rich emits a literal two-char `\\]`
sequence. The opening bracket renders cleanly but the closing renders
as `\\]`.

This probe drives `/` in chat input, captures the SVG, and scans the
visible text for `\\]` artefacts.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.widgets import ChatInput, SlashDropdown  # noqa: E402


def _mock(app):
    async def fake_get_flavors():
        return {"a": {"name": "a", "model": "m"}}

    async def fake_list_commands():
        return [{"name": "/help", "description": "help"}]

    async def fake_list_skills(flavor=None):
        return [{"name": "ci-setup", "size": 0, "loaded": False}]

    async def fake_get_tools(flavor=None):
        return {"tools": [{"name": "bash", "description": "shell"}]}

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
        ci = app.query_one(f"#input-{flavor}", ChatInput)
        slash = app.query_one(f"#slash-{flavor}", SlashDropdown)
        ci.focus()
        ci.text = "/"
        slash.update_for_text("/")
        await pilot.pause(0.4)

        svg_path = ROOT / "artifacts/v1-smoke/qa/probe_15_slash_badge_backslash.svg"
        app.save_screenshot(str(svg_path))
        svg = svg_path.read_text()
        text_only = "".join(re.findall(r">([^<]+)<", svg)).replace("&#160;", " ")

        # Post-fix: badge style switched to `( cat )` parens to avoid
        # Rich literal-bracket escape pitfalls entirely. Verify
        # no backslash leaks AND the chip glyphs render.
        if "\\]" in text_only or "\\[" in text_only:
            samples = re.findall(r".{0,5}\\[\[\]].{0,5}", text_only)
            failures.append(
                f"SVG: literal backslash-bracket present — chip render leak. "
                f"Examples: {samples[:3]}"
            )
        if "( cmd" not in text_only and "( skill" not in text_only and "( tool" not in text_only:
            failures.append(
                "SVG: no `( cmd `/`( skill `/`( tool ` chip prefix — badge mis-rendered"
            )

    print("\n".join(failures) if failures else "OK: slash badge clean")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
