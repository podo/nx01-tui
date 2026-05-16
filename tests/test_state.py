"""Unit tests for FlavorState + route_event."""

from __future__ import annotations

from nx01_tui.tui.events import parse_event
from nx01_tui.tui.state import AgentState, FlavorState, ToolStatus, route_event
from tests.fixtures.sample_events import (
    chunk,
    flavor_status,
    skill_loaded,
    thinking,
    tool_completed,
    tool_started,
    turn_done,
)


def test_chunk_appends_assistant_message():
    state = FlavorState(name="assistant")
    route_event(state, parse_event(chunk(text="hello ")))
    route_event(state, parse_event(chunk(text="world")))
    assert state.state == AgentState.STREAMING
    assert state.messages[-1]["text"] == "hello world"


def test_thinking_collected_and_sealed_on_turn_done():
    state = FlavorState(name="assistant")
    route_event(state, parse_event(thinking(text="step 1")))
    route_event(state, parse_event(thinking(text="step 2")))
    assert state.thinking_active
    assert state.state == AgentState.THINKING

    route_event(state, parse_event(turn_done()))
    assert not state.thinking_active
    assert state.state == AgentState.DONE
    block = next(m for m in state.messages if m["type"] == "thinking_block")
    assert block["lines"] == ["step 1", "step 2"]
    assert block["duration_ms"] >= 0


def test_tool_state_transitions():
    state = FlavorState(name="assistant")
    route_event(state, parse_event(tool_started(call_id="t1")))
    assert state.state == AgentState.TOOL_CALL
    assert state.tool_calls[0].status == ToolStatus.ACTIVE

    route_event(state, parse_event(tool_completed(call_id="t1")))
    assert state.tool_calls[0].status == ToolStatus.DONE
    assert state.tool_calls[0].elapsed_ms >= 0


def test_skill_loaded_records_to_sidebar_list():
    state = FlavorState(name="assistant")
    route_event(state, parse_event(skill_loaded(name="ci-setup", size=4096)))
    assert state.skills_loaded == [{"name": "ci-setup", "size": 4096}]
    assert state.messages[-1]["type"] == "skill_block"


def test_flavor_status_event_updates_status():
    state = FlavorState(name="assistant")
    route_event(state, parse_event(flavor_status(status="crashed")))
    assert state.status == "crashed"


def test_turn_done_records_token_usage():
    state = FlavorState(name="assistant")
    route_event(state, parse_event(turn_done()))
    assert state.token_usage["total"] == 150


def test_activity_summary_counts():
    state = FlavorState(name="assistant")
    state.apply_tool("bash", "ls", "started", call_id="t1")
    state.apply_tool("bash", "pwd", "completed", call_id="t2")
    state.apply_tool("bash", "x", "error", call_id="t3")
    done, active, queued = state.activity_summary()
    assert done == 1
    assert active == 1
    # error tool is neither done, active, nor queued
    assert queued == 0
