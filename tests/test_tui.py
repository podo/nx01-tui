"""Spec — #76 nx01-tui: Textual operator cockpit.

Tests are deliberately headless (no real terminal) — pure unit tests for
state/widget logic and CLI parsing. No Textual run_test() to avoid
event loop complexity in the spec suite.
"""

from __future__ import annotations


def test_flavor_state_initial():
    from nx01_tui.tui.state import FlavorState

    s = FlavorState(name="ops")
    assert s.name == "ops"
    assert s.status == "idle"
    assert s.messages == []
    assert s.thinking_lines == []
    assert not s.thinking_active
    assert s.tool_calls == []
    assert not s.scroll_locked


def test_flavor_state_apply_chunk():
    from nx01_tui.tui.state import FlavorState

    s = FlavorState(name="ops")
    s.apply_chunk("hello")
    assert s.messages[-1]["type"] == "chunk"
    assert s.messages[-1]["text"] == "hello"


def test_flavor_state_apply_chunk_concatenates():
    from nx01_tui.tui.state import FlavorState

    s = FlavorState(name="ops")
    s.apply_chunk("hello")
    s.apply_chunk(" world")
    assert len(s.messages) == 1
    assert s.messages[0]["text"] == "hello world"


def test_flavor_state_apply_thinking():
    from nx01_tui.tui.state import FlavorState

    s = FlavorState(name="ops")
    s.apply_thinking("reasoning...")
    assert s.thinking_active
    assert s.thinking_lines == ["reasoning..."]


def test_flavor_state_seal_thinking():
    from nx01_tui.tui.state import FlavorState

    s = FlavorState(name="ops")
    s.apply_thinking("line 1")
    s.apply_thinking("line 2")
    s.seal_thinking()
    assert not s.thinking_active
    assert s.messages[-1]["type"] == "thinking_block"
    assert s.messages[-1]["lines"] == ["line 1", "line 2"]


def test_flavor_state_seal_thinking_empty_noop():
    from nx01_tui.tui.state import FlavorState

    s = FlavorState(name="ops")
    s.seal_thinking()
    assert s.messages == []


def test_flavor_state_apply_tool():
    from nx01_tui.tui.state import FlavorState

    s = FlavorState(name="ops")
    s.apply_tool("Bash", "ls /app", "started")
    assert s.tool_calls[-1]["tool"] == "Bash"
    assert s.tool_calls[-1]["status"] == "started"


def test_flavor_state_seal_turn():
    from nx01_tui.tui.state import FlavorState

    s = FlavorState(name="ops")
    s.apply_tool("Bash", "ls", "done")
    s.seal_turn()
    assert s.last_turn_tools[0]["tool"] == "Bash"
    assert s.tool_calls == []
    assert not s.thinking_active


def test_route_chunk_event():
    from nx01_tui.tui.state import FlavorState, route_event

    s = FlavorState(name="ops")
    route_event(s, {"type": "AgentChunkEvent", "flavor": "ops", "text": "hi", "at": 0})
    assert s.messages[-1]["text"] == "hi"


def test_route_thinking_event():
    from nx01_tui.tui.state import FlavorState, route_event

    s = FlavorState(name="ops")
    route_event(s, {"type": "AgentThinkingEvent", "flavor": "ops", "text": "think...", "at": 0})
    assert s.thinking_active
    assert "think..." in s.thinking_lines


def test_route_turn_done_seals_thinking():
    from nx01_tui.tui.state import FlavorState, route_event

    s = FlavorState(name="ops")
    route_event(s, {"type": "AgentThinkingEvent", "flavor": "ops", "text": "t", "at": 0})
    route_event(
        s,
        {"type": "AgentTurnDoneEvent", "flavor": "ops", "stop_reason": "end_turn", "at": 0},
    )
    assert not s.thinking_active
    assert any(m["type"] == "thinking_block" for m in s.messages)


def test_route_tool_call_event():
    from nx01_tui.tui.state import FlavorState, route_event

    s = FlavorState(name="ops")
    route_event(
        s,
        {
            "type": "ToolCallEvent",
            "flavor": "ops",
            "tool": "Read",
            "title": "read file",
            "status": "started",
            "at": 0,
        },
    )
    assert s.tool_calls[-1]["tool"] == "Read"


def test_route_flavor_status_event():
    from nx01_tui.tui.state import FlavorState, route_event

    s = FlavorState(name="ops")
    route_event(s, {"type": "FlavorStatusEvent", "flavor": "ops", "status": "running", "at": 0})
    assert s.status == "running"


def test_route_ignores_wrong_flavor():
    from nx01_tui.tui.state import FlavorState, route_event

    s = FlavorState(name="ops")
    route_event(s, {"type": "AgentChunkEvent", "flavor": "research", "text": "hi", "at": 0})
    assert s.messages == []


def test_command_palette_filter_empty():
    from nx01_tui.tui.commands import filter_commands

    results = filter_commands("")
    assert len(results) > 10


def test_command_palette_filter_prefix():
    from nx01_tui.tui.commands import filter_commands

    results = filter_commands("/mo")
    assert any(r["command"] == "/model" for r in results)


def test_command_palette_filter_slash_alone():
    from nx01_tui.tui.commands import filter_commands

    results = filter_commands("/")
    assert len(results) > 10


def test_command_palette_categories():
    from nx01_tui.tui.commands import HERMES_COMMANDS

    categories = {c["category"] for c in HERMES_COMMANDS}
    assert "session" in categories
    assert "config" in categories
    assert "tools" in categories


def test_command_palette_all_have_required_keys():
    from nx01_tui.tui.commands import HERMES_COMMANDS

    for cmd in HERMES_COMMANDS:
        assert "command" in cmd
        assert "category" in cmd
        assert "description" in cmd
        assert cmd["command"].startswith("/")


def test_tui_subparser_registered():
    from nx01_tui.cli import build_parser

    args = build_parser().parse_args(["tui", "--url", "http://localhost:8000"])
    assert args.command == "tui"
    assert args.url == "http://localhost:8000"


def test_tui_subparser_api_key():
    from nx01_tui.cli import build_parser

    args = build_parser().parse_args(["tui", "--api-key", "secret"])
    assert args.api_key == "secret"


def test_tui_subparser_defaults():
    from nx01_tui.cli import build_parser

    args = build_parser().parse_args(["tui"])
    assert args.url == "http://localhost:8000"
    assert args.api_key is None
