"""tests/test_app_widgets.py — Phase 1 & 2: App lifecycle, tabs, input, command palette."""

import pytest
from textual.widgets import Input, Label, TabbedContent

from nx01_tui.tui.app import (
    CommandPalette,
    ConversationPane,
    FleetHeader,
    Nx01TuiApp,
    ToolSidebar,
)
from nx01_tui.tui.state import FlavorState

# ---------------------------------------------------------------------------
# Phase 1: App Lifecycle & Tab Management
# ---------------------------------------------------------------------------


class TestAppLifecycle:
    @pytest.mark.asyncio
    async def test_compose_yields_fleet_header(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            header = pilot.app.query_one("#fleet-header", FleetHeader)
            assert header is not None

    @pytest.mark.asyncio
    async def test_compose_yields_tabs(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            tabs = pilot.app.query_one("#tabs", TabbedContent)
            assert tabs is not None

    @pytest.mark.asyncio
    async def test_compose_yields_input(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            inp = pilot.app.query_one("#msg-input", Input)
            assert inp is not None

    @pytest.mark.asyncio
    async def test_compose_yields_flavor_badge(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            badge = pilot.app.query_one("#flavor-badge", Label)
            assert badge is not None

    @pytest.mark.asyncio
    async def test_compose_yields_command_palette(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            palette = pilot.app.query_one("#cmd-palette", CommandPalette)
            assert palette is not None
            assert not palette.is_open()

    @pytest.mark.asyncio
    async def test_on_mount_focuses_input(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            inp = pilot.app.query_one("#msg-input", Input)
            assert inp.has_focus


class TestTabCreation:
    @pytest.mark.asyncio
    async def test_first_sse_event_mounts_tab_pane(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            assert tabs.tab_count == 1
            assert tabs.active == "tab-assistant"

    @pytest.mark.asyncio
    async def test_second_flavor_creates_second_tab(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)
            pilot.app._states["operator"] = FlavorState(name="operator")
            pilot.app._mount_flavor_tab("operator")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            assert tabs.tab_count == 2

    @pytest.mark.asyncio
    async def test_tab_pane_contains_conv_and_sidebar(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            conv = pilot.app.query_one("#conv-assistant", ConversationPane)
            sidebar = pilot.app.query_one("#tools-assistant", ToolSidebar)
            assert conv is not None
            assert sidebar is not None

    @pytest.mark.asyncio
    async def test_unknown_flavor_creates_tab(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event({"type": "AgentChunkEvent", "flavor": "ghost", "text": "hi"})
            await pilot.pause(0.5)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            assert tabs.tab_count == 1
            assert "tab-ghost" in [p.id for p in tabs.query_one("ContentSwitcher").children]


class TestTabSwitching:
    @pytest.mark.asyncio
    async def test_ctrl_1_switches_to_first_tab(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)
            pilot.app._states["operator"] = FlavorState(name="operator")
            pilot.app._mount_flavor_tab("operator")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("ctrl+1")
            await pilot.pause(0.1)
            assert tabs.active == "tab-assistant"

    @pytest.mark.asyncio
    async def test_ctrl_2_switches_to_second_tab(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)
            pilot.app._states["operator"] = FlavorState(name="operator")
            pilot.app._mount_flavor_tab("operator")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("ctrl+2")
            await pilot.pause(0.1)
            assert tabs.active == "tab-operator"

    @pytest.mark.asyncio
    async def test_ctrl_3_noop_with_only_2_tabs(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)
            pilot.app._states["operator"] = FlavorState(name="operator")
            pilot.app._mount_flavor_tab("operator")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            tabs.active = "tab-assistant"
            await pilot.press("ctrl+3")
            await pilot.pause(0.1)
            assert tabs.active == "tab-assistant"

    @pytest.mark.asyncio
    async def test_ctrl_1_noop_when_no_tabs(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            tabs = pilot.app.query_one("#tabs", TabbedContent)
            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("ctrl+1")
            await pilot.pause(0.1)
            assert tabs.active == ""

    @pytest.mark.asyncio
    async def test_tab_switch_refocuses_input(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)
            pilot.app._states["operator"] = FlavorState(name="operator")
            pilot.app._mount_flavor_tab("operator")
            await pilot.pause(0.3)

            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("ctrl+2")
            await pilot.pause(0.1)
            assert inp.has_focus

    @pytest.mark.asyncio
    async def test_tab_switch_updates_flavor_badge(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.5)
            pilot.app._states["operator"] = FlavorState(name="operator")
            pilot.app._mount_flavor_tab("operator")
            await pilot.pause(0.5)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            tabs.active = "tab-operator"
            await pilot.pause(0.3)

            badge = pilot.app.query_one("#flavor-badge", Label)
            assert "operator" in str(badge.render())


# ---------------------------------------------------------------------------
# Phase 2: Input & Command Palette
# ---------------------------------------------------------------------------


class TestInputTyping:
    @pytest.mark.asyncio
    async def test_typing_appears_in_input(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("h", "e", "l", "l", "o")
            await pilot.pause(0.1)
            assert inp.value == "hello"

    @pytest.mark.asyncio
    async def test_input_clears_after_enter(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("h", "e", "l", "l", "o")
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert inp.value == ""

    @pytest.mark.asyncio
    async def test_enter_on_empty_input_does_nothing(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert inp.value == ""


class TestCommandPalette:
    @pytest.mark.asyncio
    async def test_typing_slash_opens_palette(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("/")
            await pilot.pause(0.2)
            palette = pilot.app.query_one("#cmd-palette", CommandPalette)
            assert palette.is_open()

    @pytest.mark.asyncio
    async def test_typing_non_slash_closes_palette(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("/")
            await pilot.pause(0.2)
            await pilot.press("backspace")
            await pilot.pause(0.2)
            palette = pilot.app.query_one("#cmd-palette", CommandPalette)
            assert not palette.is_open()

    @pytest.mark.asyncio
    async def test_escape_closes_palette(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("/")
            await pilot.pause(0.2)
            await pilot.press("escape")
            await pilot.pause(0.2)
            palette = pilot.app.query_one("#cmd-palette", CommandPalette)
            assert not palette.is_open()


class TestEscapeBehavior:
    @pytest.mark.asyncio
    async def test_escape_clears_input(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("h", "e", "l", "l", "o")
            await pilot.press("escape")
            await pilot.pause(0.2)
            assert inp.value == ""


class TestEndKey:
    @pytest.mark.asyncio
    async def test_end_key_resumes_scroll(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            conv = pilot.app.query_one("#conv-assistant", ConversationPane)
            conv._scroll_locked = True
            await pilot.press("ctrl+end")
            await pilot.pause(0.3)
            assert conv._scroll_locked is False
