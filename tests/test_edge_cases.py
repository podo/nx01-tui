"""tests/test_edge_cases.py — Phase 7: Edge cases and resilience."""

import pytest
from textual.widgets import Input

from nx01_tui.tui.state import FlavorState

# ---------------------------------------------------------------------------
# FlavorState edge cases
# ---------------------------------------------------------------------------


class TestFlavorStateEdgeCases:
    def test_seal_thinking_empty_noop(self):
        s = FlavorState(name="ops")
        s.seal_thinking()
        assert s.messages == []

    def test_apply_chunk_concatenates(self):
        s = FlavorState(name="ops")
        s.apply_chunk("hello")
        s.apply_chunk(" world")
        assert len(s.messages) == 1
        assert s.messages[0]["text"] == "hello world"

    def test_multiple_seal_turn_calls(self):
        s = FlavorState(name="ops")
        s.apply_tool("Bash", "ls", "done")
        s.seal_turn()
        s.apply_tool("Read", "file", "done")
        s.seal_turn()
        assert len(s.last_turn_tools) == 1

    def test_apply_tool_without_title(self):
        s = FlavorState(name="ops")
        s.apply_tool("Bash", "", "started")
        assert s.tool_calls[-1]["tool"] == "Bash"
        assert s.tool_calls[-1]["arg"] == ""

    def test_apply_tool_with_title_not_arg(self):
        s = FlavorState(name="ops")
        s.apply_tool("Read", "file content here", "done")
        assert s.tool_calls[-1]["arg"] == "file content here"


class TestRouteEventEdgeCases:
    def test_unknown_event_type_no_crash(self):
        s = FlavorState(name="ops")
        from nx01_tui.tui.state import route_event

        route_event(s, {"type": "UnknownEvent", "flavor": "ops"})
        assert s.messages == []

    def test_missing_flavor_field_no_crash(self):
        s = FlavorState(name="ops")
        from nx01_tui.tui.state import route_event

        route_event(s, {"type": "AgentChunkEvent"})
        assert s.messages == []

    def test_chunk_empty_not_added(self):
        s = FlavorState(name="ops")
        s.apply_chunk("hello")
        s.apply_chunk("")
        assert len(s.messages) == 1
        assert s.messages[0]["text"] == "hello"

    def test_chunk_after_seal_merges_with_last(self):
        s = FlavorState(name="ops")
        s.apply_chunk("hello")
        s.apply_chunk("world")
        s.apply_thinking("reasoning")
        s.seal_turn()
        assert len(s.messages) == 2
        assert s.messages[0]["type"] == "chunk"
        assert "helloworld" in s.messages[0]["text"]


# ---------------------------------------------------------------------------
# Command palette edge cases
# ---------------------------------------------------------------------------


class TestCommandPaletteEdgeCases:
    def test_filter_no_matches(self):
        from nx01_tui.tui.commands import filter_commands

        results = filter_commands("/xyznotfound")
        assert results == []

    def test_filter_case_insensitive(self):
        from nx01_tui.tui.commands import filter_commands

        results = filter_commands("/MO")
        assert any(r["command"] == "/model" for r in results)

    def test_filter_slash_alone_returns_all(self):
        from nx01_tui.tui.commands import filter_commands

        results = filter_commands("/")
        assert len(results) > 10

    def test_filter_empty_string_returns_all(self):
        from nx01_tui.tui.commands import filter_commands

        results = filter_commands("")
        assert len(results) > 10


# ---------------------------------------------------------------------------
# App edge cases
# ---------------------------------------------------------------------------


class TestAppEdgeCases:
    @pytest.mark.asyncio
    async def test_on_key_no_tabs_no_crash(self):
        from nx01_tui.tui.app import Nx01TuiApp

        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("ctrl+1")
            await pilot.press("ctrl+2")
            await pilot.press("ctrl+3")
            await pilot.press("ctrl+4")
            await pilot.pause(0.2)

    @pytest.mark.asyncio
    async def test_on_key_palette_open_does_not_crash(self):
        from nx01_tui.tui.app import Nx01TuiApp

        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.5)

            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()

            await pilot.press("/")
            await pilot.pause(0.2)

            palette = pilot.app.query_one("#cmd-palette")
            assert palette.is_open

    @pytest.mark.asyncio
    async def test_dispatch_to_unknown_flavor_no_crash(self):
        from nx01_tui.tui.app import Nx01TuiApp

        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._dispatch_to_pane(
                "ghost", {"type": "AgentChunkEvent", "flavor": "ghost", "text": "hi"}
            )
            await pilot.pause(0.2)

    @pytest.mark.asyncio
    async def test_handle_event_unknown_flavor_creates_tab(self):
        from textual.widgets import TabbedContent

        from nx01_tui.tui.app import Nx01TuiApp

        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event(
                {"type": "AgentChunkEvent", "flavor": "new-flavor", "text": "hi"}
            )
            await pilot.pause(0.5)
            tabs = pilot.app.query_one("#tabs", TabbedContent)
            panes = list(tabs.query_one("ContentSwitcher").children)
            assert "tab-new-flavor" in [p.id for p in panes]

    @pytest.mark.asyncio
    async def test_multiple_chunk_events_in_log(self):
        from textual.widgets import RichLog

        from nx01_tui.tui.app import ConversationPane, Nx01TuiApp

        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            pilot.app._dispatch_to_pane(
                "assistant",
                {"type": "AgentChunkEvent", "flavor": "assistant", "text": "hello", "at": 0},
            )
            pilot.app._dispatch_to_pane(
                "assistant",
                {"type": "AgentChunkEvent", "flavor": "assistant", "text": " world", "at": 0},
            )
            await pilot.pause(0.2)

            conv = pilot.app.query_one("#conv-assistant", ConversationPane)
            log = conv.query_one(RichLog)
            assert any("hello" in str(strip) for strip in log.lines)
            assert any("world" in str(strip) for strip in log.lines)


# ---------------------------------------------------------------------------
# State per-flavor isolation
# ---------------------------------------------------------------------------


class TestStateIsolation:
    def test_each_flavor_state_is_independent(self):
        s1 = FlavorState(name="assistant")
        s2 = FlavorState(name="operator")
        s1.apply_chunk("msg for A")
        s2.apply_chunk("msg for B")
        assert s1.messages[0]["text"] == "msg for A"
        assert s2.messages[0]["text"] == "msg for B"

    def test_seal_turn_isolated_per_flavor(self):
        s1 = FlavorState(name="assistant")
        s2 = FlavorState(name="operator")
        s1.apply_tool("ToolA", "arg", "done")
        s2.apply_tool("ToolB", "arg", "done")
        s1.seal_turn()
        assert len(s1.last_turn_tools) == 1
        assert len(s2.tool_calls) == 1
        assert len(s2.last_turn_tools) == 0
