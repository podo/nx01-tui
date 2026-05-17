"""Probe: MonitorSidebar responsive behaviour across breakpoints.

Verifies item 3: hide below 130 cols; clamp to [MIN_WIDTH, MAX_WIDTH] above.
Expected:
  80   → hidden
  110  → hidden
  129  → hidden
  130  → visible, width = max(30, min(50, 130//4)) = 32
  160  → visible, width = max(30, min(50, 160//4)) = 40
  200  → visible, width = max(30, min(50, 200//4)) = 50
  240  → visible, width clamped at 50
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.widgets.sidebar import MonitorSidebar  # noqa: E402


def _mock(app):
    async def fake_get_flavors():
        return {"a": {"name": "a", "model": "m"}}

    async def fake_list_commands():
        return [{"name": "/h", "description": "h"}]

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
    cases = [
        (80, "hidden", 0),
        (110, "hidden", 0),
        (129, "hidden", 0),
        (130, "visible", 32),
        (160, "visible", 40),
        (200, "visible", 50),
        (240, "visible", 50),
    ]
    app = Nx01App("http://mock", api_key="t", flavors=["a"])
    _mock(app)
    async with app.run_test(size=(240, 50)) as pilot:
        await pilot.pause(1.0)
        sb = app.query_one(MonitorSidebar)
        for width, expected_state, expected_w in cases:
            sb.apply_terminal_width(width)
            await pilot.pause(0.05)
            hidden = sb.has_class("hidden")
            actual_w = int(sb.styles.width.value) if (sb.styles.width and not hidden) else 0
            if expected_state == "hidden" and not hidden:
                failures.append(f"width={width}: expected hidden, got visible (w={actual_w})")
            if expected_state == "visible":
                if hidden:
                    failures.append(f"width={width}: expected visible, got hidden")
                elif actual_w != expected_w:
                    failures.append(f"width={width}: expected w={expected_w}, got w={actual_w}")
            # icon-strip class should never be applied (item 3 removed it)
            if sb.has_class("icon-strip"):
                failures.append(f"width={width}: .icon-strip class present (should be removed)")

    print("\n".join(failures) if failures else "OK: sidebar breakpoint probe PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
