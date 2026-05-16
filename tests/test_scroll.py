"""tests/test_scroll.py — Phase 4: Scroll lock, badge, per-flavor state."""

import pytest
from textual.widgets import Label, TabbedContent

from nx01_tui.tui.app import ConversationPane, Nx01TuiApp
from nx01_tui.tui.state import FlavorState


class TestScrollLock:
    @pytest.mark.asyncio
    async def test_scroll_up_engages_lock(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            conv = pilot.app.query_one("#conv-assistant", ConversationPane)
            conv._scroll_locked = True
            assert conv._scroll_locked is True

    @pytest.mark.asyncio
    async def test_end_key_resumes_scroll(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            conv = pilot.app.query_one("#conv-assistant", ConversationPane)
            conv._scroll_locked = True
            badge = conv.query_one("#new-badge", Label)
            badge.add_class("visible")

            await pilot.press("ctrl+end")
            await pilot.pause(0.5)

            assert conv._scroll_locked is False
            assert "visible" not in badge.classes

    @pytest.mark.asyncio
    async def test_new_content_badge_appears_when_locked(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            conv = pilot.app.query_one("#conv-assistant", ConversationPane)
            conv._scroll_locked = True
            badge = conv.query_one("#new-badge", Label)
            badge.add_class("visible")
            assert "visible" in badge.classes


class TestPerFlavorScrollLock:
    @pytest.mark.asyncio
    async def test_scroll_lock_per_tab(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)
            pilot.app._states["operator"] = FlavorState(name="operator")
            pilot.app._mount_flavor_tab("operator")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            tabs.active = "tab-assistant"
            await pilot.pause(0.1)

            conv_a = pilot.app.query_one("#conv-assistant", ConversationPane)
            pilot.app.query_one("#conv-operator", ConversationPane)

            conv_a._scroll_locked = True
            tabs.active = "tab-operator"
            await pilot.pause(0.2)

            assert conv_a._scroll_locked is True

    @pytest.mark.asyncio
    async def test_badge_per_tab(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)
            pilot.app._states["operator"] = FlavorState(name="operator")
            pilot.app._mount_flavor_tab("operator")
            await pilot.pause(0.3)

            conv_a = pilot.app.query_one("#conv-assistant", ConversationPane)
            conv_o = pilot.app.query_one("#conv-operator", ConversationPane)

            badge_a = conv_a.query_one("#new-badge", Label)
            badge_o = conv_o.query_one("#new-badge", Label)

            badge_a.add_class("visible")
            assert "visible" in badge_a.classes
            assert "visible" not in badge_o.classes

    @pytest.mark.asyncio
    async def test_end_only_resumes_active_tab(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)
            pilot.app._states["operator"] = FlavorState(name="operator")
            pilot.app._mount_flavor_tab("operator")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            tabs.active = "tab-operator"
            await pilot.pause(0.1)

            conv_a = pilot.app.query_one("#conv-assistant", ConversationPane)
            conv_o = pilot.app.query_one("#conv-operator", ConversationPane)

            conv_a._scroll_locked = True
            conv_o._scroll_locked = True

            await pilot.press("ctrl+end")
            await pilot.pause(0.5)

            assert conv_o._scroll_locked is False
            assert conv_a._scroll_locked is True
