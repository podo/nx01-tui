"""tests/test_app_events.py — Phase 3: SSE event dispatching, multi-flavor routing."""

import pytest
from textual.widgets import RichLog, TabbedContent

from nx01_tui.tui.app import ConversationPane, Nx01TuiApp, ToolSidebar
from nx01_tui.tui.state import FlavorState


def make_chunk(flavor: str, text: str) -> dict:
    return {"type": "AgentChunkEvent", "flavor": flavor, "text": text, "at": 0}


def make_thinking(flavor: str, text: str) -> dict:
    return {"type": "AgentThinkingEvent", "flavor": flavor, "text": text, "at": 0}


def make_done(flavor: str) -> dict:
    return {"type": "AgentTurnDoneEvent", "flavor": flavor, "stop_reason": "end_turn", "at": 0}


def make_tool(flavor: str, tool: str, title: str, status: str) -> dict:
    return {
        "type": "ToolCallEvent",
        "flavor": flavor,
        "tool": tool,
        "title": title,
        "status": status,
        "at": 0,
    }


def make_status(flavor: str, status: str) -> dict:
    return {"type": "FlavorStatusEvent", "flavor": flavor, "status": status, "at": 0}


def log_contains(log: RichLog, text: str) -> bool:
    return any(text in str(strip) for strip in log.lines)


# ---------------------------------------------------------------------------
# Phase 3: SSE Event Dispatching
# ---------------------------------------------------------------------------


class TestEventRouting:
    @pytest.mark.asyncio
    async def test_chunk_appends_to_conversation(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.5)

            pilot.app._dispatch_to_pane("assistant", make_chunk("assistant", "hello"))
            await pilot.pause(0.3)

            conv = pilot.app.query_one("#conv-assistant", ConversationPane)
            log = conv.query_one(RichLog)
            assert log_contains(log, "hello")

    @pytest.mark.asyncio
    async def test_thinking_event_creates_thinking_block(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.5)

            pilot.app._dispatch_to_pane("assistant", make_thinking("assistant", "reasoning..."))
            await pilot.pause(0.3)

            conv = pilot.app.query_one("#conv-assistant", ConversationPane)
            assert conv._active_thinking is not None

    @pytest.mark.asyncio
    async def test_turn_done_event_seals_thinking(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.5)

            pilot.app._dispatch_to_pane("assistant", make_thinking("assistant", "reasoning..."))
            pilot.app._dispatch_to_pane("assistant", make_done("assistant"))
            await pilot.pause(0.3)

            conv = pilot.app.query_one("#conv-assistant", ConversationPane)
            assert conv._active_thinking is None

    @pytest.mark.asyncio
    async def test_tool_event_adds_to_sidebar(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.5)

            pilot.app._dispatch_to_pane(
                "assistant", make_tool("assistant", "Bash", "ls /app", "started")
            )
            await pilot.pause(0.3)

            sidebar = pilot.app.query_one("#tools-assistant", ToolSidebar)
            assert len(sidebar.query(".tool-entry")) == 1

    @pytest.mark.asyncio
    async def test_flavor_status_event_updates_state(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event(make_chunk("assistant", "hi"))
            await pilot.pause(0.5)

            pilot.app._handle_event(make_status("assistant", "running"))
            await pilot.pause(0.3)

            state = pilot.app._states["assistant"]
            assert state.status == "running"

    @pytest.mark.asyncio
    async def test_wrong_flavor_events_ignored(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event(make_chunk("assistant", "from assistant"))
            await pilot.pause(0.5)

            pilot.app._handle_event(make_chunk("ghost", "hello"))
            await pilot.pause(0.3)

            log_a = pilot.app.query_one("#conv-assistant", ConversationPane).query_one(RichLog)
            assert not log_contains(log_a, "hello")


# ---------------------------------------------------------------------------
# Multi-Flavor Routing
# ---------------------------------------------------------------------------


class TestMultiFlavorTabCreation:
    @pytest.mark.asyncio
    async def test_first_event_creates_tab(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event(make_chunk("assistant", "hi"))
            await pilot.pause(0.5)
            tabs = pilot.app.query_one("#tabs", TabbedContent)
            panes = list(tabs.query_one("ContentSwitcher").children)
            assert "tab-assistant" in [p.id for p in panes]

    @pytest.mark.asyncio
    async def test_second_flavor_creates_second_tab(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event(make_chunk("assistant", "hi"))
            await pilot.pause(0.3)
            pilot.app._handle_event(make_chunk("operator", "hi"))
            await pilot.pause(0.5)
            tabs = pilot.app.query_one("#tabs", TabbedContent)
            assert tabs.tab_count == 2

    @pytest.mark.asyncio
    async def test_events_route_to_correct_pane(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event(make_chunk("assistant", "from assistant"))
            await pilot.pause(0.3)
            pilot.app._handle_event(make_chunk("operator", "from operator"))
            await pilot.pause(0.5)

            state_a = pilot.app._states["assistant"]
            state_o = pilot.app._states["operator"]
            assert any("from assistant" in m["text"] for m in state_a.messages)
            assert any("from operator" in m["text"] for m in state_o.messages)

    @pytest.mark.asyncio
    async def test_unknown_flavor_creates_own_tab(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event(make_chunk("ghost", "hello"))
            await pilot.pause(0.5)
            tabs = pilot.app.query_one("#tabs", TabbedContent)
            assert tabs.tab_count == 1
            assert "tab-ghost" in [p.id for p in tabs.query_one("ContentSwitcher").children]


class TestMultiFlavorStateIsolation:
    @pytest.mark.asyncio
    async def test_each_flavor_has_independent_messages(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event(make_chunk("assistant", "msg for A"))
            await pilot.pause(0.3)
            pilot.app._handle_event(make_chunk("operator", "msg for B"))
            await pilot.pause(1.0)

            state_a = pilot.app._states["assistant"]
            state_o = pilot.app._states["operator"]
            assert any("msg for A" in m["text"] for m in state_a.messages)
            assert any("msg for B" in m["text"] for m in state_o.messages)

    @pytest.mark.asyncio
    async def test_each_flavor_has_independent_thinking(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event(make_thinking("assistant", "A thinking"))
            await pilot.pause(0.3)
            pilot.app._handle_event(make_thinking("operator", "B thinking"))
            await pilot.pause(0.5)

            conv_a = pilot.app.query_one("#conv-assistant", ConversationPane)
            conv_o = pilot.app.query_one("#conv-operator", ConversationPane)
            assert conv_a._active_thinking is not None
            assert conv_o._active_thinking is not None

    @pytest.mark.asyncio
    async def test_each_flavor_has_independent_tool_log(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event(make_tool("assistant", "Read", "read file A", "done"))
            await pilot.pause(0.3)
            pilot.app._handle_event(make_tool("operator", "Bash", "run cmd B", "done"))
            await pilot.pause(0.5)

            sidebar_a = pilot.app.query_one("#tools-assistant", ToolSidebar)
            sidebar_o = pilot.app.query_one("#tools-operator", ToolSidebar)
            assert len(sidebar_a.query(".tool-entry")) == 1
            assert len(sidebar_o.query(".tool-entry")) == 1


class TestMultiFlavorInterleaved:
    @pytest.mark.asyncio
    async def test_interleaved_events_from_two_flavors(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._handle_event(make_chunk("assistant", "A chunk 1"))
            await pilot.pause(0.3)
            pilot.app._handle_event(make_chunk("operator", "B chunk 1"))
            await pilot.pause(0.3)
            pilot.app._handle_event(make_thinking("assistant", "A thinking"))
            await pilot.pause(0.3)
            pilot.app._handle_event(make_tool("operator", "Bash", "ls", "done"))
            await pilot.pause(1.0)

            state_a = pilot.app._states["assistant"]
            state_o = pilot.app._states["operator"]
            assert any("A chunk 1" in m["text"] for m in state_a.messages)
            assert any("B chunk 1" in m["text"] for m in state_o.messages)

            sidebar_o = pilot.app.query_one("#tools-operator", ToolSidebar)
            assert len(sidebar_o.query(".tool-entry")) == 1
