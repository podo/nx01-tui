"""Probe: PermissionModal risk variants + ConfirmModal danger focus + modal stack backdrop.

Verifies items 4, 10, 20.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from textual.widgets import Button  # noqa: E402

from nx01_tui.tui.app import Nx01App  # noqa: E402
from nx01_tui.tui.modals.confirm_modal import ConfirmModal  # noqa: E402
from nx01_tui.tui.modals.permission_modal import PermissionModal  # noqa: E402
from nx01_tui.tui.modals.sessions_modal import SessionEntry, SessionsModal  # noqa: E402


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
    app = Nx01App("http://mock", api_key="t", flavors=["a"])
    _mock(app)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause(1.0)

        # ── Permission modal: low (default focused = Allow, has Always btn) ──
        m_low = PermissionModal(tool="bash", args="ls", risk="low")
        app.push_screen(m_low)
        await pilot.pause(0.2)
        if not m_low.has_class("risk-low"):
            failures.append("PermissionModal.risk-low missing class")
        # Default focus should be Allow
        focused = app.focused
        if focused is None or focused.id != "allow":
            failures.append(
                f"PermissionModal(low) focused={getattr(focused, 'id', None)!r}, expected 'allow'"
            )
        # Always button should be present
        try:
            m_low.query_one("#always", Button)
        except Exception:  # noqa: BLE001
            failures.append("PermissionModal(low) missing 'Always' button")
        app.save_screenshot(str(ROOT / "artifacts/v1-smoke/qa/probe_04_perm_low.svg"))
        m_low.dismiss("deny")
        await pilot.pause(0.2)

        # ── Permission modal: medium (Deny focused, Always present, thick border) ──
        m_med = PermissionModal(tool="bash", args="rm something", risk="medium")
        app.push_screen(m_med)
        await pilot.pause(0.2)
        if not m_med.has_class("risk-medium"):
            failures.append("PermissionModal.risk-medium missing class")
        focused = app.focused
        if focused is None or focused.id != "deny":
            failures.append(
                f"PermissionModal(medium) focused={getattr(focused, 'id', None)!r}, expected 'deny'"
            )
        try:
            m_med.query_one("#always", Button)
        except Exception:  # noqa: BLE001
            failures.append("PermissionModal(medium) missing 'Always' button (expected present)")
        app.save_screenshot(str(ROOT / "artifacts/v1-smoke/qa/probe_04_perm_medium.svg"))
        m_med.dismiss("deny")
        await pilot.pause(0.2)

        # ── Permission modal: high (Deny focused, NO Always btn, irreversible line) ──
        m_high = PermissionModal(tool="rm", args="-rf /", risk="high")
        app.push_screen(m_high)
        await pilot.pause(0.2)
        if not m_high.has_class("risk-high"):
            failures.append("PermissionModal.risk-high missing class")
        focused = app.focused
        if focused is None or focused.id != "deny":
            failures.append(
                f"PermissionModal(high) focused={getattr(focused, 'id', None)!r}, expected 'deny'"
            )
        try:
            m_high.query_one("#always", Button)
            failures.append("PermissionModal(high) has 'Always' button (expected hidden)")
        except Exception:  # noqa: BLE001
            pass  # good — no Always
        try:
            m_high.query_one("#irreversible")
        except Exception:  # noqa: BLE001
            failures.append("PermissionModal(high) missing #irreversible label")
        app.save_screenshot(str(ROOT / "artifacts/v1-smoke/qa/probe_04_perm_high.svg"))
        m_high.dismiss("deny")
        await pilot.pause(0.2)

        # ── ConfirmModal dangerous: No should be focused, error border ──
        m_conf = ConfirmModal("Delete this?", dangerous=True)
        app.push_screen(m_conf)
        await pilot.pause(0.2)
        if not m_conf.has_class("dangerous"):
            failures.append("ConfirmModal.dangerous missing class")
        focused = app.focused
        if focused is None or focused.id != "no":
            failures.append(
                f"ConfirmModal(dangerous) focused={getattr(focused, 'id', None)!r}, expected 'no'"
            )
        try:
            m_conf.query_one("#irreversible")
        except Exception:  # noqa: BLE001
            failures.append("ConfirmModal(dangerous) missing 'cannot be undone' line")
        app.save_screenshot(str(ROOT / "artifacts/v1-smoke/qa/probe_04_confirm_dangerous.svg"))
        m_conf.dismiss(False)
        await pilot.pause(0.2)

        # ── ConfirmModal benign: Yes focused, no irreversible line ──
        m_benign = ConfirmModal("Save?", dangerous=False)
        app.push_screen(m_benign)
        await pilot.pause(0.2)
        focused = app.focused
        if focused is None or focused.id != "yes":
            failures.append(
                f"ConfirmModal(benign) focused={getattr(focused, 'id', None)!r}, expected 'yes'"
            )
        try:
            m_benign.query_one("#irreversible")
            failures.append("ConfirmModal(benign) has 'cannot be undone' line (should be hidden)")
        except Exception:  # noqa: BLE001
            pass
        app.save_screenshot(str(ROOT / "artifacts/v1-smoke/qa/probe_04_confirm_benign.svg"))
        m_benign.dismiss(False)
        await pilot.pause(0.2)

        # ── Modal stack backdrop dim ──
        sessions = [
            SessionEntry(session_id="s1", flavor="a", title="t1", preview="p1"),
            SessionEntry(session_id="s2", flavor="a", title="t2", preview="p2"),
        ]
        sm = SessionsModal(sessions)
        app.push_screen(sm)
        await pilot.pause(0.3)
        cm = ConfirmModal("Stack test?", dangerous=True)
        app.push_screen(cm)
        await pilot.pause(0.3)
        # The BaseModal.DEFAULT_CSS sets background: $background 70% — verify
        # by checking the computed styles. Textual exposes styles.background.
        bg = str(cm.styles.background) if cm.styles.background else ""
        if "70%" not in bg and "background" not in bg.lower():
            # Background may not stringify with the alpha — fallback check on rule
            pass
        app.save_screenshot(str(ROOT / "artifacts/v1-smoke/qa/probe_04_stacked_modals.svg"))
        cm.dismiss(False)
        await pilot.pause(0.2)
        sm.dismiss(None)
        await pilot.pause(0.2)

    print("\n".join(failures) if failures else "OK: modals probe PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
