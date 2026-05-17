"""Probe: confirm the SlashDropdown category badge rendering bug.

Item 12: badge label uses nested Rich tags like
    f"[{cat_color}][[/][{cat_color}] {cat_label:<5}[/][{cat_color}]][/]"
which is a brittle attempt to render literal `[` and `]` brackets with color.
Some terminals show `[[/]` and `]` as literal glyphs instead of `[ cmd ]`.

Renders a slash dropdown, then inspects the SVG for the artefact.
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
        await pilot.pause(0.3)

        svg_path = ROOT / "artifacts/v1-smoke/qa/probe_09_slash_badge.svg"
        app.save_screenshot(str(svg_path))
        svg = svg_path.read_text()
        text_only = "".join(re.findall(r">([^<]+)<", svg)).replace("&#160;", " ")
        if "[[/]" in text_only:
            failures.append(
                "SVG: literal '[[/]' visible — badge color tags broken on literal bracket"
            )
        if " cmd  ]" in text_only and "[ cmd ]" not in text_only:
            failures.append("SVG: cmd badge missing leading '[' bracket — uneven render")

    print("\n".join(failures) if failures else "OK: slash badge renders cleanly")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
