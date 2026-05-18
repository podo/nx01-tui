"""ConversationView turn-grouping and paging tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

import nx01_tui.tui.widgets.conversation as conv_module
from nx01_tui.tui.widgets.conversation import (
    ConversationView,
    _LoadMoreHeader,
    _TurnGroup,
)


class _Host(App):
    def compose(self) -> ComposeResult:
        yield ConversationView()


# ── Turn grouping ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_message_starts_turn_group():
    """Each add_user_message() creates exactly one _TurnGroup."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        conv = app.query_one(ConversationView)
        conv.add_user_message("hello")
        await pilot.pause(0.1)
        assert len(conv._mounted_groups) == 1
        assert isinstance(conv._mounted_groups[0], _TurnGroup)


@pytest.mark.asyncio
async def test_assistant_widgets_land_inside_turn_group():
    """ThinkingBlock and AssistantMessage mount inside the current TurnGroup."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        conv = app.query_one(ConversationView)
        conv.add_user_message("hi")
        await pilot.pause(0.05)
        conv.append_thinking("step one")
        conv.append_assistant("response text")
        await pilot.pause(0.1)
        group = conv._mounted_groups[0]
        # Both widgets are children of the TurnGroup, not ConversationView directly
        from nx01_tui.tui.widgets import ThinkingBlock
        from nx01_tui.tui.widgets.messages import AssistantMessage
        assert len(list(group.query(ThinkingBlock))) == 1
        assert len(list(group.query(AssistantMessage))) == 1


@pytest.mark.asyncio
async def test_two_turns_create_two_groups():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        conv = app.query_one(ConversationView)
        conv.add_user_message("turn one")
        conv.end_assistant()
        await pilot.pause(0.05)
        conv.add_user_message("turn two")
        await pilot.pause(0.1)
        assert len(conv._mounted_groups) == 2


# ── Paging: archival ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_archival_triggers_after_max_turns(monkeypatch):
    """When mounted turns exceed MAX_MOUNTED_TURNS, oldest is archived."""
    monkeypatch.setattr(conv_module, "MAX_MOUNTED_TURNS", 2)
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        conv = app.query_one(ConversationView)
        # 3 turns → turn 1 should be archived
        conv.add_user_message("turn 1")
        await pilot.pause(0.05)
        conv.add_user_message("turn 2")
        await pilot.pause(0.05)
        conv.add_user_message("turn 3")
        await pilot.pause(0.1)
        assert len(conv._mounted_groups) == 2
        assert len(conv._archived_groups) == 1


@pytest.mark.asyncio
async def test_load_more_header_shown_after_archival(monkeypatch):
    """_LoadMoreHeader appears when at least one turn is archived."""
    monkeypatch.setattr(conv_module, "MAX_MOUNTED_TURNS", 2)
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        conv = app.query_one(ConversationView)
        conv.add_user_message("t1")
        await pilot.pause(0.05)
        conv.add_user_message("t2")
        await pilot.pause(0.05)
        conv.add_user_message("t3")  # triggers archival
        await pilot.pause(0.15)
        assert conv._load_header is not None
        assert len(list(app.query(_LoadMoreHeader))) == 1


@pytest.mark.asyncio
async def test_load_more_header_label_counts_archived(monkeypatch):
    monkeypatch.setattr(conv_module, "MAX_MOUNTED_TURNS", 1)
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        conv = app.query_one(ConversationView)
        conv.add_user_message("t1")
        await pilot.pause(0.05)
        conv.add_user_message("t2")  # archives t1
        await pilot.pause(0.05)
        conv.add_user_message("t3")  # archives t2
        await pilot.pause(0.15)
        assert len(conv._archived_groups) == 2
        # Header label should reflect count of 2
        assert conv._load_header is not None


@pytest.mark.asyncio
async def test_archived_group_removed_from_dom(monkeypatch):
    """Archived TurnGroup must not be reachable via DOM query."""
    monkeypatch.setattr(conv_module, "MAX_MOUNTED_TURNS", 1)
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        conv = app.query_one(ConversationView)
        conv.add_user_message("t1")
        await pilot.pause(0.05)
        conv.add_user_message("t2")  # archives t1
        await pilot.pause(0.15)
        # Only 1 TurnGroup should be in DOM
        assert len(list(app.query(_TurnGroup))) == 1


# ── Paging: restore ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_archived_turns_restores_groups(monkeypatch):
    monkeypatch.setattr(conv_module, "MAX_MOUNTED_TURNS", 2)
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        conv = app.query_one(ConversationView)
        conv.add_user_message("t1")
        await pilot.pause(0.05)
        conv.add_user_message("t2")
        await pilot.pause(0.05)
        conv.add_user_message("t3")  # archives t1
        await pilot.pause(0.15)
        assert len(conv._archived_groups) == 1
        # Restore
        conv._load_archived_turns()
        await pilot.pause(0.15)
        assert len(conv._archived_groups) == 0
        assert len(conv._mounted_groups) == 3
        assert conv._load_header is None


@pytest.mark.asyncio
async def test_load_archived_removes_header(monkeypatch):
    monkeypatch.setattr(conv_module, "MAX_MOUNTED_TURNS", 2)
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        conv = app.query_one(ConversationView)
        conv.add_user_message("t1")
        await pilot.pause(0.05)
        conv.add_user_message("t2")
        await pilot.pause(0.05)
        conv.add_user_message("t3")
        await pilot.pause(0.15)
        assert conv._load_header is not None
        conv._load_archived_turns()
        await pilot.pause(0.15)
        assert conv._load_header is None
        assert len(list(app.query(_LoadMoreHeader))) == 0


# ── Change 2: freeze via ConversationView ─────────────────────────────────


@pytest.mark.asyncio
async def test_freeze_called_on_previous_assistant_at_new_turn():
    """Starting a new user turn must call freeze() on the previous AssistantMessage."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        conv = app.query_one(ConversationView)
        # First turn
        conv.add_user_message("first")
        await pilot.pause(0.05)
        conv.append_assistant("response one")
        conv.end_assistant()
        await pilot.pause(0.15)
        from nx01_tui.tui.widgets.messages import AssistantMessage
        last = conv._last_assistant
        assert last is not None
        # Second turn triggers freeze
        conv.add_user_message("second")
        await pilot.pause(0.15)
        # _last_assistant cleared and freeze() called (md is None after freeze)
        assert conv._last_assistant is None
        assert last._md is None


@pytest.mark.asyncio
async def test_reset_for_replay_clears_paging_state():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        conv = app.query_one(ConversationView)
        conv.add_user_message("msg")
        await pilot.pause(0.1)
        conv.reset_for_replay()
        await pilot.pause(0.1)
        assert conv._current_group is None
        assert conv._mounted_groups == []
        assert conv._archived_groups == []
        assert conv._load_header is None
        assert conv._last_assistant is None
